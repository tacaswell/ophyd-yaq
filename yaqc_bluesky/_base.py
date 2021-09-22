__all__ = ["Base"]


from collections import OrderedDict
import threading
import time
from typing import Dict

from ._status import Status


class Base:
    def __init__(self, yaq_client, *, name=None):
        self.yaq_client = yaq_client
        self.yaq_traits = yaq_client.traits
        self.yaq_name = self.yaq_client.id()["name"]
        if name is None:
            self.name = self.yaq_name
        else:
            self.name = name
        self.parent = None
        self._lock = threading.Lock()

    def _describe(self, out):
        for key, defn in self.yaq_client._protocol.get("fields", {}).items():
            if key == "origin":
                continue
            if not defn["fields"]["dynamic"]:
                continue
            out[f"{self.name}_{key}"] = self._field_metadata
            if defn["fields"]["type"] in ["int", "float", "double"]:
                out[f"{self.name}_{key}"]["dtype"] = "number"
            elif defn["fields"]["type"] == "string":
                out[f"{self.name}_{key}"]["dtype"] = "string"
            else:
                out[f"{self.name}_{key}"]["dtype"] = "array"
                # TODO shape?
        return out

    def describe(self) -> OrderedDict:
        out: OrderedDict = OrderedDict()
        out = self._describe(out)
        return out

    def describe_configuration(self) -> OrderedDict:
        out: OrderedDict = OrderedDict()
        for key, defn in self.yaq_client._protocol.get("fields", {}).items():
            if key == "origin":
                continue
            if defn["fields"]["dynamic"]:
                continue
            out[f"{self.name}_{key}"] = self._field_metadata
            if defn["fields"]["type"] in ["int", "float", "double"]:
                out[f"{self.name}_{key}"]["dtype"] = "number"
            elif defn["fields"]["type"] == "string":
                out[f"{self.name}_{key}"]["dtype"] = "string"
            else:
                out[f"{self.name}_{key}"]["dtype"] = "array"
                # TODO shape?

        return out

    @property
    def _field_metadata(self) -> OrderedDict:
        """Metadata to be shared by all fields for this daemon."""
        out: OrderedDict = OrderedDict()
        out["source"] = f"yaq:{self.yaq_name}"
        out["yaq_port"] = self.yaq_client._port
        out["yaq_host"] = self.yaq_client._host
        out["shape"] = tuple()  # should be None, but upstream bluesky is broken
        return out

    @property
    def hints(self) -> Dict:
        out: Dict = {}
        out["fields"] = []
        return out

    def _read(self, out, ts) -> OrderedDict:
        for key, defn in self.yaq_client._protocol.get("fields", {}).items():
            if key == "origin":
                continue
            if not defn["fields"]["dynamic"]:
                continue
            getter = defn["fields"]["getter"]
            out[f"{self.name}_{key}"] = {
                "value": getattr(self.yaq_client, getter)(),
                "timestamp": ts,
            }
        return out

    def read(self) -> OrderedDict:
        with self._lock:
            out: OrderedDict = OrderedDict()
            ts = time.time()
            out = self._read(out, ts)
        return out

    def read_configuration(self) -> OrderedDict:
        out = OrderedDict()
        ts = time.time()
        for key, defn in self.yaq_client._protocol.get("fields", {}).items():
            if key == "origin":
                continue
            if defn["fields"]["dynamic"]:
                continue
            getter = defn["fields"]["getter"]
            out[f"{self.name}_{key}"] = {
                "value": getattr(self.yaq_client, getter)(),
                "timestamp": ts,
            }
        return out

    def trigger(self) -> Status:
        # should be overloaded for those devices that need a trigger
        st = Status()
        st._finished()
        return st

    def _wait_until_still(self):
        st = Status()

        def poll():
            while True:
                if self.yaq_client.busy():
                    time.sleep(0.1)
                else:
                    break
            st._finished()

        threading.Thread(target=poll).start()
        return st
