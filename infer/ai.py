from subprocess import Popen, PIPE
import aiohttp
import json
import atexit

class AI():
    def __init__(self, model, port, remote=False):
        self.server = f"http://{model if remote else '127.0.0.1'}:{port}"
        self.params = {"temp": 0.7, "mirostat": 1, "mirostat_ent": 4, "mirostat_lr": 0.2, "ignore_eos": True, "repeat_penalty": 1.35, "repeat_last_n": 1600}
        if remote: return
        p = Popen(["./server", "-c", "4096", "--mlock", "-ngl", "99", "-cb", "-m", model, "--host", "127.0.0.1", "--port", port], stdout=PIPE)
        atexit.register(lambda: p.kill())
        while "listening" not in str(p.stdout.readline(), "utf8"): continue

    async def init(self):
        self.sess = aiohttp.ClientSession()
    
    async def tokenize(self, prompt):
        async with self.sess.post(self.server + "/tokenize", json={"content": prompt}) as resp:
            return await resp.json()
    
    async def completion(self, prompt, **kwargs):
        r = []
        async with self.sess.post(self.server + "/completion", json={"prompt": prompt, "cache_prompt": True, "stream": True, **kwargs, **self.params}) as resp:
            async for line in resp.content:
                if line == b"\n": continue
                d = json.loads(str(line, "utf8").split("data: ")[1])
                if "stopfn" in kwargs and kwargs["stopfn"](d): break
                r.append(d)
                if "n_predict" in kwargs and len(r) >= kwargs["n_predict"]: break
        return r
