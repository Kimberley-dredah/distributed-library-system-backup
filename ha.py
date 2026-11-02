
import os
import json
import time
import uuid
import threading
import urllib.request


LEASE_KEY = "library:ha:leader"
EPOCH_KEY = "library:ha:epoch"

LEASE_MS = 15000
RENEW_SECONDS = 3
MIN_VALID_MS = 4000


class HAController:
    def __init__(self, node_id, startup_delay=0):
        self.node_id = node_id
        self.startup_delay = startup_delay

        self.url = os.environ.get("UPSTASH_REDIS_REST_URL")
        self.token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

        if not self.url or not self.token:
            raise RuntimeError("Upstash credentials are missing.")

        self.url = self.url.rstrip("/")
        self.owner = node_id + ":" + uuid.uuid4().hex

        self.lease_token = None
        self.leader = False
        self.lock = threading.Lock()
        self.running = False

    def redis(self, command):
        req = urllib.request.Request(
            self.url,
            data=json.dumps(command).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=4) as response:
            result = json.loads(response.read().decode("utf-8"))

        if "error" in result:
            raise RuntimeError(str(result["error"]))

        return result.get("result")

    def acquire(self):
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then
            local epoch = redis.call('INCR', KEYS[2])
            local value = ARGV[1] .. ':' .. epoch
            redis.call('PSETEX', KEYS[1], ARGV[2], value)
            return value
        end
        return ''
        """

        result = self.redis([
            "EVAL", script, "2",
            LEASE_KEY, EPOCH_KEY,
            self.owner, str(LEASE_MS)
        ])

        return result or None

    def renew(self, lease_token):
        script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            return redis.call('PEXPIRE', KEYS[1], ARGV[2])
        end
        return 0
        """

        result = self.redis([
            "EVAL", script, "1",
            LEASE_KEY, lease_token, str(LEASE_MS)
        ])

        return result == 1

    def verify(self, lease_token):
        script = """
        if redis.call('GET', KEYS[1]) == ARGV[1] then
            local ttl = redis.call('PTTL', KEYS[1])
            if ttl > tonumber(ARGV[2]) then
                return ttl
            end
        end
        return 0
        """

        result = self.redis([
            "EVAL", script, "1",
            LEASE_KEY, lease_token, str(MIN_VALID_MS)
        ])

        return isinstance(result, (int, float)) and result > MIN_VALID_MS

    def is_leader(self):
        with self.lock:
            lease_token = self.lease_token

        if not lease_token:
            return False

        try:
            valid = self.verify(lease_token)
        except Exception:
            valid = False

        with self.lock:
            self.leader = valid

        return valid

    def run(self):
        time.sleep(self.startup_delay)

        while self.running:
            try:
                with self.lock:
                    lease_token = self.lease_token

                if lease_token:
                    if self.renew(lease_token):
                        with self.lock:
                            self.leader = True
                        print(self.node_id, "leadership renewed")
                    else:
                        with self.lock:
                            self.lease_token = None
                            self.leader = False
                        print(self.node_id, "leadership lost")

                else:
                    new_token = self.acquire()

                    if new_token:
                        with self.lock:
                            self.lease_token = new_token
                            self.leader = True
                        print(self.node_id, "became leader")
                    else:
                        with self.lock:
                            self.leader = False
                        print(self.node_id, "is standby")

            except Exception as error:
                with self.lock:
                    self.leader = False
                print(self.node_id, "cannot verify leadership:", error)

            time.sleep(RENEW_SECONDS)

    def start(self):
        if self.running:
            return

        self.running = True

        threading.Thread(
            target=self.run,
            daemon=True
        ).start()
