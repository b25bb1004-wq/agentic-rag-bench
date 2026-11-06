#!/usr/bin/env python3
"""Run one named plan of agentic-rag-bench unattended on a Kaggle GPU (T4 x2).

Every step writes a JSON marker to out/steps.jsonl, every command has a hard timeout, and the
driver stops starting new steps when the session budget runs low, so finished results always
land in /kaggle/working/out. Lead-owned.

  python kaggle/driver.py smoke
"""
import glob
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("RB_OUT", "/kaggle/working/out"))
SCR = Path(os.environ.get("RB_SCRATCH", "/tmp/rb"))
LLAMA = SCR / "llama.cpp"
LLAMA_TAG = "b11669"  # commit 620d2225c, the llama-server build used for every Mac run
PY = sys.executable
T0 = time.time()
BUDGET_S = float(os.environ.get("RB_HOURS", "8.0")) * 3600
SERVERS = {}
# Evaluation serving: one slot per server. With 4 slots CUDA gave 30/40 identical rows across identical runs
# (batch composition changes the math); with 1 slot 40/40, at 1.35x the time (det kernel, 2026-11-04).
EVAL = dict(ctx=6144, slots=1, cache_ram=0)


def left():
    return BUDGET_S - (time.time() - T0)


LOCK = threading.Lock()


def mark(step, status, **info):
    record = dict(step=step, status=status, t=round(time.time() - T0), **info)
    with LOCK, open(OUT / "steps.jsonl", "a") as handle:
        handle.write(json.dumps(record) + "\n")
        print("##", json.dumps(record), flush=True)


def lanes(*jobs):
    """Run independent job lists in parallel threads (one per GPU) and wait for all."""
    def guarded(job):
        try:
            job()
        except Exception as error:  # one lane failing must not kill the other lane's results
            mark(getattr(job, "__name__", "lane"), "crash", error=repr(error)[:300])
    threads = [threading.Thread(target=guarded, args=(job,)) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def sh(name, cmd, timeout, env=None, cwd=REPO):
    """Run a command with a hard timeout; never raises, returns True on exit code 0."""
    timeout = min(timeout, max(60, left() - 300))  # never run past the session budget
    started = time.time()
    with open(OUT / "logs" / f"{name}.log", "w") as log:
        try:
            rc = subprocess.run(cmd, shell=isinstance(cmd, str), stdout=log, stderr=subprocess.STDOUT,
                                timeout=timeout, cwd=cwd, env={**os.environ, **(env or {})}).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    mark(name, "ok" if rc == 0 else "fail", rc=rc, secs=round(time.time() - started))
    return rc == 0


def need(seconds, step):
    """Skip a step that cannot finish inside the remaining budget."""
    if left() < seconds:
        mark(step, "skipped", reason=f"needs {seconds}s, {round(left())}s left")
        return False
    return True


# ---------- setup ----------

def setup():
    for d in (OUT / "logs", OUT / "results", OUT / "adapters", SCR / "cfg", SCR / "models"):
        d.mkdir(parents=True, exist_ok=True)
    sh("env", "nvidia-smi; df -h /tmp /kaggle/working; free -g; nproc; " + PY + " -V; " + PY +
       " -c 'import torch;print(torch.__version__, torch.version.cuda, torch.cuda.device_count())'", 120)
    ok = sh("pip", [PY, "-m", "pip", "install", "-q", "transformers==5.19.0", "peft==0.21.2", "accelerate==1.15.0",
                    "rank-bm25==0.2.2", "sentencepiece", "protobuf", "pyyaml"], 1200)
    # Kaggle preinstalls torchao 0.10; peft 0.21 refuses to wrap any layer while it is importable (smoke v3)
    sh("pip_rm_torchao", [PY, "-m", "pip", "uninstall", "-y", "torchao"], 300)
    return ok


def build_llama():
    # The clone is needed even with cached binaries: convert_hf_to_gguf.py and gguf-py come from it.
    if not (LLAMA / ".git").exists():
        if not sh("llama_clone", ["git", "clone", "--depth", "1", "--branch", LLAMA_TAG,
                                  "https://github.com/ggml-org/llama.cpp", str(LLAMA)], 600, cwd=SCR):
            return False
    server = LLAMA / "build" / "bin" / "llama-server"
    cached = glob.glob("/kaggle/input/**/llama-bin.tar.gz", recursive=True)
    if cached and sh("llama_unpack", ["tar", "-xzf", cached[0], "-C", str(LLAMA)], 300) and server.exists():
        return sh("llama_version", [str(server), "--version"], 60)
    base = ["cmake", "-B", "build", "-DGGML_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES=75", "-DLLAMA_CURL=OFF",
            "-DCMAKE_BUILD_TYPE=Release"]
    # Kaggle ships libcuda only as a stub; without it CUDA::cuda_driver is missing (failed 2026-11-04)
    ok = sh("llama_cmake", base + ["-DCMAKE_LIBRARY_PATH=/usr/local/cuda/lib64/stubs"], 600, cwd=LLAMA)
    if not ok:
        shutil.rmtree(LLAMA / "build", ignore_errors=True)
        ok = sh("llama_cmake_novmm", base + ["-DGGML_CUDA_NO_VMM=ON"], 600, cwd=LLAMA)
    ok = ok and sh("llama_build", ["cmake", "--build", "build", "--target", "llama-server", "-j", "4"], 3000, cwd=LLAMA)
    if ok:  # cache the binaries as kernel output so later sessions skip the build
        sh("llama_pack", ["tar", "-czf", str(OUT / "llama-bin.tar.gz"), "build/bin"], 600, cwd=LLAMA)
    return ok and sh("llama_version", [str(server), "--version"], 60)


def hf_download(repo, dest):
    if (dest / "config.json").exists():
        return True
    code = f"from huggingface_hub import snapshot_download; snapshot_download({repo!r}, local_dir={str(dest)!r}, max_workers=8)"
    if sh(f"dl_{dest.name}", [PY, "-c", code], 1800):
        return True
    return sh(f"dl_{dest.name}_noxet", [PY, "-c", code], 1800, env={"HF_HUB_DISABLE_XET": "1"})


def to_gguf(hf_dir, gguf, name):
    if gguf.exists():
        return True
    return sh(f"convert_{name}", [PY, str(LLAMA / "convert_hf_to_gguf.py"), str(hf_dir), "--outtype", "q8_0",
                                  "--outfile", str(gguf)], 2400, env={"PYTHONPATH": str(LLAMA / "gguf-py")})


# ---------- serving and runs ----------

def serve(gguf, gpu, port, ctx=24576, slots=4, cache_ram=256):
    stop(port)
    log = open(OUT / "logs" / f"server_{port}_{Path(gguf).stem}.log", "a")
    SERVERS[port] = subprocess.Popen(
        [str(LLAMA / "build" / "bin" / "llama-server"), "-m", str(gguf), "--port", str(port), "-ngl", "99",
         "-c", str(ctx), "-np", str(slots), "--jinja", "--cache-ram", str(cache_ram)],
        stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "CUDA_VISIBLE_DEVICES": str(gpu)})
    for _ in range(180):
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status == 200:
                mark(f"serve_{port}", "ok", model=Path(gguf).name, gpu=gpu)
                return True
        except Exception:
            pass
        if SERVERS[port].poll() is not None:
            break
        time.sleep(2)
    mark(f"serve_{port}", "fail", model=Path(gguf).name, gpu=gpu)
    stop(port)
    return False


def stop(port=None):
    for p in [port] if port else list(SERVERS):
        proc = SERVERS.pop(p, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                proc.kill()


def run_cfg(cfg, port, name=None, limit=None, timeout=3 * 3600, **override):
    """Run configs/<cfg>.yaml against the server on <port>; results go to out/results/<name>."""
    config = yaml.safe_load((REPO / "configs" / f"{cfg}.yaml").read_text())
    config.update(override)
    config["name"] = name or config["name"]
    config["workers"] = override.get("workers", 1)  # one request at a time per single-slot server
    config["llm"] = dict(config.get("llm") or {}, base_url=f"http://127.0.0.1:{port}")
    config["out_dir"] = str(OUT / "results" / config["name"])
    path = SCR / "cfg" / f"{config['name']}.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    cmd = [PY, "-W", "ignore", "-m", "ragbench.run", "--config", str(path)] + (["--limit", str(limit)] if limit else [])
    cmd += ["--mock"] if os.environ.get("RB_MOCK") else []  # local plumbing test without a model
    return sh(f"run_{config['name']}", cmd, timeout)


def train(name, base_hf, gpus, sft_args=(), split=False, max_len=2048, epochs=2.0, head=None, timeout=4 * 3600):
    """make_sft -> fp16amp LoRA -> merge -> GGUF q8_0. Returns the GGUF path or None."""
    work = SCR / "models" / name
    work.mkdir(parents=True, exist_ok=True)
    sft, adapter, gguf = work / "sft.jsonl", work / "adapter", work / f"{name}.gguf"
    saved = OUT / "adapters" / name
    if (saved / "adapter_config.json").exists() and not head:  # trained in an earlier session (restore)
        shutil.copytree(saved, adapter, dirs_exist_ok=True)
        mark(f"train_{name}", "reused")
        return merge_convert(name, base_hf, adapter, work, gguf)
    if not sh(f"sft_{name}", [PY, "-W", "ignore", "-m", "ragbench.make_sft", "--out", str(sft), *sft_args], 600):
        return None
    if head:  # smoke only: train on the first <head> records
        lines = sft.read_text().splitlines(keepends=True)[:head]
        sft.write_text("".join(lines))
    cmd = [PY, "-W", "ignore", "-m", "ragbench.train_lora", "--base", str(base_hf), "--data", str(sft),
           "--out", str(adapter), "--epochs", str(epochs), "--lr", "2e-4", "--rank", "16", "--alpha", "32",
           "--max_len", str(max_len), "--bs", "1", "--grad_accum", "8", "--seed", "0", "--precision", "fp16amp"]
    if not sh(f"train_{name}", cmd + (["--split_gpus"] if split else []), timeout,
              env={"CUDA_VISIBLE_DEVICES": gpus, "RAGBENCH_TOKENIZER": str(base_hf)}):
        return None
    shutil.copytree(adapter, saved, dirs_exist_ok=True)  # small; keeps the trained weights
    return merge_convert(name, base_hf, adapter, work, gguf)


def done_rows(name):
    path = OUT / "results" / name / "seed0.jsonl"
    return sum(1 for _ in path.open()) if path.exists() else 0


def merge_convert(name, base_hf, adapter, work, gguf):
    merged = work / "merged_hf"
    code = f"from ragbench.merge_export import merge; merge({str(base_hf)!r}, {str(adapter)!r}, {str(merged)!r})"
    if not sh(f"merge_{name}", [PY, "-W", "ignore", "-c", code], 1800, env={"CUDA_VISIBLE_DEVICES": ""}):
        return None
    ok = to_gguf(merged, gguf, name)
    shutil.rmtree(merged, ignore_errors=True)
    return gguf if ok else None


def determinism(name_a, name_b):
    """Compare answers of two identical runs row by row (greedy decoding under -np 4 on CUDA)."""
    def load(name):
        rows = [json.loads(l) for l in open(OUT / "results" / name / "seed0.jsonl")]
        return {(r["category"], r["case_id"] or r["qid"]): (r["answer"], r["citations"]) for r in rows}
    a, b = load(name_a), load(name_b)
    keys = sorted(set(a) & set(b))
    same = sum(a[k] == b[k] for k in keys)
    mark("determinism", "ok" if keys and same == len(keys) else "differs", same=same, n=len(keys))


# ---------- plans ----------

def plan_smoke():
    """About 1.5 h: build, 1.7B serve + determinism + timing, fp16amp training slice, C2 pipeline, 8B speed."""
    if not (setup() and build_llama()):
        return
    b17 = SCR / "models" / "qwen3-1.7b"
    g17 = SCR / "models" / "qwen3-1.7b-q8_0.gguf"
    if not (hf_download("Qwen/Qwen3-1.7B", b17) and to_gguf(b17, g17, "base17") and serve(g17, 0, 8080)):
        return
    run_cfg("s17_react_c0", 8080, name="smoke17_c0_a", limit=40, timeout=1800)
    run_cfg("s17_react_c0", 8080, name="smoke17_c0_b", limit=40, timeout=1800)
    determinism("smoke17_c0_a", "smoke17_c0_b")
    run_cfg("s17_plan_c0", 8080, name="smoke17_plan_c0", limit=24, timeout=1800)
    if need(1800, "smoke_train17"):
        gguf = train("smoke_c2_17", b17, "1", head=40, epochs=1.0, timeout=1800)
        if gguf and serve(gguf, 1, 8081):
            run_cfg("s17_react_c2", 8081, name="smoke17_c2", limit=12, timeout=1200)
    stop()
    b8 = SCR / "models" / "qwen3-8b"
    g8 = SCR / "models" / "qwen3-8b-q8_0.gguf"
    if need(2400, "smoke_8b") and hf_download("Qwen/Qwen3-8B", b8) and to_gguf(b8, g8, "base8") and serve(g8, 0, 8080):
        run_cfg("s17_react_c0", 8080, name="smoke8_react_c0", limit=24, timeout=1800)
        sh("smoke8_episodes_plan", [PY, "-W", "ignore", "-m", "ragbench.make_episodes", "--agent", "plan", "--base-url",
                                    "http://127.0.0.1:8080", "--n", "12", "--workers", "4", "--out",
                                    str(OUT / "results" / "smoke8_episodes_plan.jsonl")], 1800)
        stop()
        if need(1500, "smoke_train8"):
            train("smoke_c2_8b", b8, "0,1", split=True, head=24, epochs=1.0, max_len=3072, timeout=1500)
    stop()


def restore():
    """Copy data, results and adapters from earlier sessions' outputs (kernel_sources) so runs resume."""
    for steps in glob.glob("/kaggle/input/**/out/steps.jsonl", recursive=True):
        previous = Path(steps).parent
        for part in ("data", "results", "adapters"):
            if (previous / part).is_dir():
                shutil.copytree(previous / part, OUT / part, dirs_exist_ok=True)
        mark("restore", "ok", source=str(previous))


def episodes(agent, port, n, out_name, timeout):
    out = OUT / "data" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    ok = sh(f"episodes_{out_name}", [PY, "-W", "ignore", "-m", "ragbench.make_episodes", "--agent", agent, "--base-url",
                                      f"http://127.0.0.1:{port}", "--n", str(n), "--workers", "4", "--out", str(out),
                                      "--resume"], timeout)
    return out if ok else None


def poison_eval(kind, cond):
    # same shape as the Mac poison configs: 100 clean questions, no attack cases
    return dict(condition=f"{cond}_poison_{kind}_k5", n_clean=100, n_per_category=0)


def plan_s17():
    """Qwen3-1.7B on Kaggle. GPU0: Plan episodes, Plan C0/C1 (+poison). GPU1: ReAct fact-k5 C2 (for Mac eval),
    Plan C2 (+poison, served on GPU1), then the C2 poison sweep (k 1 and 25, adapters for Mac eval)."""
    if not (setup() and build_llama()):
        return
    restore()
    b17, g17 = SCR / "models" / "qwen3-1.7b", SCR / "models" / "qwen3-1.7b-q8_0.gguf"
    if not (hf_download("Qwen/Qwen3-1.7B", b17) and to_gguf(b17, g17, "base17")):
        return
    plan_eps = OUT / "data" / "episodes_plan17.jsonl"
    ready, attempted = threading.Event(), threading.Event()

    def gpu0():
        try:
            if not serve(g17, 0, 8080):
                return
            if episodes("plan", 8080, 1200, plan_eps.name, timeout=5 * 3600):
                ready.set()
        finally:
            attempted.set()  # lane B stops waiting even if this lane failed
        if not serve(g17, 0, 8080, **EVAL):
            return
        run_cfg("s17_plan_c0", 8080, name="k17_plan_c0")
        if ready.is_set():
            memory = {"episodes_path": str(plan_eps), "k": 3}
            run_cfg("s17_plan_c0", 8080, name="k17_plan_c1", condition="c1", memory=memory)
            for kind in ("habit", "fact"):
                run_cfg("s17_plan_c0", 8080, name=f"k17_plan_c1_poison_{kind}_k5", memory=memory, **poison_eval(kind, "c1"))
        # ReAct on the same hardware, so S1 (ReAct vs Plan) never mixes Mac and Kaggle rows
        run_cfg("s17_react_c0", 8080, name="k17_react_c0")
        run_cfg("s17_react_c0", 8080, name="k17_react_c1", condition="c1")
        stop(8080)

    def gpu1():
        # primary endpoint 2's missing arm first; its adapter is merged and evaluated on the Mac
        train("c2_poison_fact_k5", b17, "1", sft_args=["--poison-kind", "fact", "--k", "5"])
        sweep = [("habit", 1), ("fact", 25), ("habit", 25), ("fact", 1)]
        while sweep and not attempted.is_set() and left() > 3 * 3600:
            kind, k = sweep.pop(0)
            train(f"c2_poison_{kind}_k{k}", b17, "1", sft_args=["--poison-kind", kind, "--k", str(k)])
        attempted.wait(timeout=max(0, left() - 2 * 3600))
        if need(5400, "train_react_c2"):
            gguf = train("react_c2", b17, "1")
            if gguf and serve(gguf, 1, 8081, **EVAL):
                run_cfg("s17_react_c0", 8081, name="k17_react_c2", condition="c2")
                stop(8081)
        if ready.is_set():
            for name, extra, cfg in (("plan_c2", [], dict(condition="c2")),
                                     ("plan_c2_poison_habit_k5", ["--poison-kind", "habit", "--k", "5"], poison_eval("habit", "c2")),
                                     ("plan_c2_poison_fact_k5", ["--poison-kind", "fact", "--k", "5"], poison_eval("fact", "c2"))):
                if not need(5400, f"train_{name}"):
                    break
                gguf = train(name, b17, "1", max_len=3072,
                             sft_args=["--episodes", str(plan_eps), "--agent", "plan", *extra])
                if gguf and serve(gguf, 1, 8081, **EVAL):
                    run_cfg("s17_plan_c0", 8081, name=f"k17_{name}", **cfg)
                    stop(8081)
        for kind, k in sweep:
            if need(3600, f"train_c2_poison_{kind}_k{k}"):
                train(f"c2_poison_{kind}_k{k}", b17, "1", sft_args=["--poison-kind", kind, "--k", str(k)])

    lanes(gpu0, gpu1)


def base8():
    b8, g8 = SCR / "models" / "qwen3-8b", SCR / "models" / "qwen3-8b-q8_0.gguf"
    return (b8, g8) if hf_download("Qwen/Qwen3-8B", b8) and to_gguf(b8, g8, "base8") else (None, None)


def drain(jobs, port):
    """Pull (config, name, overrides) jobs from a shared queue until it is empty or time runs short."""
    while left() > 1800:
        try:
            cfg, name, override = jobs.get_nowait()
        except queue.Empty:
            return
        run_cfg(cfg, port, name=name, **override)


SIZE8 = dict(n_clean=int(os.environ.get("RB_N_CLEAN8", "150")), n_per_category=int(os.environ.get("RB_N_CAT8", "80")))


def plan_s8a():
    """Qwen3-8B inference session. Each GPU serves the base model; each lane first builds one agent's own
    episodes (train split, first 1200), then both lanes drain a shared queue: C0, oracle, budget sweep (S2),
    and each agent's C1 and C1 poison k5 once its episodes exist."""
    if not (setup() and build_llama()):
        return
    restore()
    b8, g8 = base8()
    if not g8:
        return
    jobs = queue.Queue()
    for agent in ("react", "plan"):
        jobs.put((f"s17_{agent}_c0", f"k8_{agent}_c0", dict(SIZE8)))
    jobs.put(("s17_react_c0_oracle", "k8_react_c0_oracle", dict(SIZE8)))
    for budget in (1, 2, 3, 4):
        jobs.put(("s17_react_c0", f"k8_react_c0_budget{budget}", dict(SIZE8, agent_kwargs={"max_searches": budget})))

    def lane(agent, gpu, port):
        if not serve(g8, gpu, port):
            return
        eps = episodes(agent, port, 1200, f"episodes_{agent}8b.jsonl", timeout=5 * 3600)
        if not serve(g8, gpu, port, **EVAL):
            return
        if eps:
            memory = {"episodes_path": str(eps), "k": 3}
            jobs.put((f"s17_{agent}_c0", f"k8_{agent}_c1", dict(SIZE8, condition="c1", memory=memory)))
            for kind in ("habit", "fact"):
                jobs.put((f"s17_{agent}_c0", f"k8_{agent}_c1_poison_{kind}_k5", dict(memory=memory, **poison_eval(kind, "c1"))))
        drain(jobs, port)
        stop(port)

    lanes(lambda: lane("react", 0, 8080), lambda: lane("plan", 1, 8081))


def plan_s8b():
    """Qwen3-8B training session: C2 for both agents (LoRA layer-split over both GPUs, one at a time), then each
    merged model is served on its own GPU for evaluation; poison k5 variants follow while time allows."""
    if not (setup() and build_llama()):
        return
    restore()
    b8, _ = base8()
    if not b8:
        return
    variants = [(agent, suffix, extra) for suffix, extra in (("", []), ("_poison_habit_k5", ["--poison-kind", "habit", "--k", "5"]),
                                                           ("_poison_fact_k5", ["--poison-kind", "fact", "--k", "5"]))
                for agent in ("react", "plan")]
    for i in range(0, len(variants), 2):  # train a react/plan pair, then evaluate the pair in parallel
        built = []
        for agent, suffix, extra in variants[i:i + 2]:
            eps = OUT / "data" / f"episodes_{agent}8b.jsonl"
            if done_rows(f"k8_{agent}_c2{suffix}") >= (100 if suffix else 600):
                mark(f"k8_{agent}_c2{suffix}", "already done")
                continue
            if eps.exists() and need(7200, f"train_c2_8b_{agent}{suffix}"):
                gguf = train(f"c2_8b_{agent}{suffix}", b8, "0,1", split=True, max_len=4096,
                             sft_args=["--episodes", str(eps), "--agent", agent, *extra])
                if gguf:
                    built.append((agent, suffix, gguf))

        def evaluate(agent, suffix, gguf, gpu, port):
            if serve(gguf, gpu, port, **EVAL):
                cfg = dict(SIZE8, condition="c2") if not suffix else poison_eval(suffix.split("_")[2], "c2")
                run_cfg(f"s17_{agent}_c0", port, name=f"k8_{agent}_c2{suffix}", **cfg)
                stop(port)
        lanes(*[lambda a=a, s=s, g=g, n=n: evaluate(a, s, g, n, 8080 + n) for n, (a, s, g) in enumerate(built)])


def plan_det():
    """About 40 min: where does CUDA nondeterminism come from (smoke v3: 34/40 identical with 4 slots and the
    prompt cache)? Fresh server per run, no prompt cache, 4 slots vs 1 slot. GPU1 meanwhile re-tests fp16amp
    training without torchao; then the 8B layer-split training slice."""
    if not (setup() and build_llama()):
        return
    b17, g17 = SCR / "models" / "qwen3-1.7b", SCR / "models" / "qwen3-1.7b-q8_0.gguf"
    if not (hf_download("Qwen/Qwen3-1.7B", b17) and to_gguf(b17, g17, "base17")):
        return

    def gpu0():
        for arm, slots in (("np4", 4), ("np1", 1)):
            for rep in "ab":
                if serve(g17, 0, 8080, ctx=6144 * slots, slots=slots, cache_ram=0):
                    run_cfg("s17_react_c0", 8080, name=f"det_{arm}_{rep}", limit=40, timeout=2400, workers=slots)
                    stop(8080)
            determinism(f"det_{arm}_a", f"det_{arm}_b")

    def gpu1():
        gguf = train("smoke_c2_17", b17, "1", head=40, epochs=1.0, timeout=1800)
        if gguf and serve(gguf, 1, 8081):
            run_cfg("s17_react_c2", 8081, name="smoke17_c2", limit=12, timeout=1200)
            stop(8081)

    lanes(gpu0, gpu1)
    b8, _ = base8()
    if b8 and need(1500, "smoke_train8"):
        train("smoke_c2_8b", b8, "0,1", split=True, head=24, epochs=1.0, max_len=4096, timeout=1500)


def plan_judge32():
    """Pre-registered fallback judge: Qwen3-32B Q4_K_M (official GGUF) split over both T4s, single slot, STRICT
    prompt, scored on the 100 blind items; validated against the adjudicator labels on the 45 review items."""
    if not (setup() and build_llama()):
        return
    gguf = SCR / "models" / "Qwen3-32B-Q4_K_M.gguf"
    code = ("from huggingface_hub import hf_hub_download; hf_hub_download('Qwen/Qwen3-32B-GGUF', "
            f"'Qwen3-32B-Q4_K_M.gguf', local_dir={str(gguf.parent)!r})")
    if not (gguf.exists() or sh("dl_qwen3-32b", [PY, "-c", code], 2400)):
        return
    if serve(gguf, "0,1", 8080, ctx=8192, slots=1, cache_ram=0):
        out = OUT / "results" / "judge32_items_scored.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        if sh("judge32", [PY, "-W", "ignore", "-m", "ragbench.judge_items", "--strict", "--base-url",
                          "http://127.0.0.1:8080", "--out", str(out)], 3600):
            sh("judge32_compare", [PY, "-W", "ignore", "-m", "ragbench.judge_items", "--compare", str(out),
                                   "data/judge_validation.jsonl"], 120)
        stop(8080)


PLANS = {"smoke": plan_smoke, "judge32": plan_judge32, "det": plan_det, "s17": plan_s17, "s8a": plan_s8a, "s8b": plan_s8b}

if __name__ == "__main__":
    plan = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "logs").mkdir(parents=True, exist_ok=True)
    version = (REPO / "kaggle" / "VERSION").read_text().strip() if (REPO / "kaggle" / "VERSION").exists() else "unknown"
    mark("plan", "start", plan=plan, budget_h=BUDGET_S / 3600, repo=version)
    try:
        PLANS[plan]()
    finally:
        stop()
        mark("plan", "end", plan=plan)
