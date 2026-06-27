import subprocess
import csv
import tempfile
import os

class ITraceProvider:
    def query(self, sql: str) -> list:
        raise NotImplementedError

class PerfettoProvider(ITraceProvider):
    def __init__(self, tp_bin_path: str, trace_path: str):
        self.tp_bin_path = tp_bin_path
        self.trace_path = trace_path

    def query(self, sql: str) -> list:
        fd, temp_path = tempfile.mkstemp(suffix=".sql")
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(sql)
            
            cmd = [self.tp_bin_path, "-q", temp_path, self.trace_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Trace Processor Error: {result.stderr}")
            
            lines = result.stdout.strip().split('\n')
            if not lines or not lines[0]:
                return []
            
            # The output uses double quotes properly, csv.DictReader handles it.
            reader = csv.DictReader(lines)
            return list(reader)
        finally:
            os.remove(temp_path)
