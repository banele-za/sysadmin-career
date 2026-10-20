"""A minimal QMP client.

QMP (QEMU Machine Protocol) is how programs control a running QEMU: one
JSON object per line over a socket. A session looks like this:

    QEMU -> {"QMP": {"version": ...}}                 greeting
    us   -> {"execute": "qmp_capabilities"}           leave negotiation mode
    QEMU -> {"return": {}}
    us   -> {"execute": "query-status", "id": 1}
    QEMU -> {"return": {"status": "running", ...}, "id": 1}
    QEMU -> {"event": "STOP", ...}                    events arrive any time

Long operations such as snapshots run as background "jobs": the command
returns immediately and we watch JOB_STATUS_CHANGE events until it finishes.
"""

import asyncio
import itertools
import json


class QMPError(Exception):
    pass


class QMPClient:
    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future] = {}   # id -> future for its reply
        self._events: asyncio.Queue = asyncio.Queue()
        self._read_task: asyncio.Task | None = None

    async def connect(self, port: int, timeout: float = 30.0) -> None:
        """Connect to QEMU's QMP port, retrying while QEMU starts up."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            try:
                self._reader, self._writer = await asyncio.open_connection("127.0.0.1", port)
                break
            except OSError:
                if asyncio.get_running_loop().time() > deadline:
                    raise
                await asyncio.sleep(0.2)
        greeting = json.loads(await self._reader.readline())
        if "QMP" not in greeting:
            raise QMPError(f"unexpected greeting: {greeting}")
        self._read_task = asyncio.create_task(self._read_loop())
        await self.execute("qmp_capabilities")

    async def _read_loop(self) -> None:
        """Route each incoming line to the command that's waiting for it, or to the event queue."""
        try:
            while line := await self._reader.readline():
                msg = json.loads(line)
                if "event" in msg:
                    await self._events.put(msg)
                elif "id" in msg and msg["id"] in self._pending:
                    self._pending.pop(msg["id"]).set_result(msg)
        finally:
            # QEMU closed the socket: fail anything still waiting.
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(QMPError("QMP connection closed"))
            self._pending.clear()

    async def execute(self, command: str, **arguments):
        """Run one QMP command and return its "return" value."""
        msg_id = next(self._ids)
        msg = {"execute": command, "id": msg_id}
        if arguments:
            msg["arguments"] = arguments
        fut = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        self._writer.write(json.dumps(msg).encode() + b"\n")
        await self._writer.drain()
        reply = await fut
        if "error" in reply:
            raise QMPError(f"{command}: {reply['error'].get('desc', reply['error'])}")
        return reply.get("return")

    async def run_job(self, command: str, job_id: str, timeout: float, **arguments) -> None:
        """Start a job-based command and wait until it concludes; raise if it failed."""
        # Drop stale events so we only see this job's progress.
        while not self._events.empty():
            self._events.get_nowait()
        await self.execute(command, **{"job-id": job_id, **arguments})

        async def wait_concluded():
            while True:
                event = await self._events.get()
                data = event.get("data", {})
                if (event["event"] == "JOB_STATUS_CHANGE" and data.get("id") == job_id
                        and data.get("status") == "concluded"):
                    return

        await asyncio.wait_for(wait_concluded(), timeout)
        jobs = await self.execute("query-jobs")
        job = next((j for j in jobs if j["id"] == job_id), {})
        await self.execute("job-dismiss", id=job_id)
        if job.get("error"):
            raise QMPError(f"{command} failed: {job['error']}")

    async def close(self) -> None:
        if self._writer:
            self._writer.close()
        if self._read_task:
            self._read_task.cancel()
