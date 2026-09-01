/**
 * Node test for subscribeJob. Not part of the Vite app tsconfig.
 * Run from repo: node --experimental-strip-types --test web/jobs.subscribe.test.mjs
 */
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { afterEach, test } from "node:test";

class FakeEventSource extends EventEmitter {
  url;
  closed = false;
  static instances = [];

  constructor(url) {
    super();
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type, listener) {
    this.on(type, listener);
  }

  close() {
    this.closed = true;
  }

  emitNativeError() {
    this.emit("error", {});
  }
}

function lastSource() {
  const src = FakeEventSource.instances.at(-1);
  assert.ok(src, "expected an EventSource");
  return src;
}

afterEach(() => {
  FakeEventSource.instances = [];
});

test("native EventSource errors eventually reject instead of hanging", async () => {
  const { JobStreamError, subscribeJob } = await import("./src/api/jobs.ts");
  const promise = subscribeJob("job-1", {
    eventSourceCtor: FakeEventSource,
    maxNativeErrors: 2,
    fetchJob: async () => {
      throw new Error("poll failed");
    },
  });

  lastSource().emitNativeError();
  lastSource().emitNativeError();

  await assert.rejects(promise, (err) => {
    assert.ok(err instanceof JobStreamError);
    assert.match(err.message, /disconnected|stream/i);
    return true;
  });
  assert.equal(lastSource().closed, true);
});

test("after bounded native errors, poll a completed job and resolve", async () => {
  const { subscribeJob } = await import("./src/api/jobs.ts");
  const promise = subscribeJob("job-9", {
    eventSourceCtor: FakeEventSource,
    maxNativeErrors: 1,
    fetchJob: async () => ({
      job_id: "job-9",
      kind: "ideas",
      status: "done",
      result: { ideas: ["A"], run_id: "r1" },
      error: null,
    }),
  });

  lastSource().emitNativeError();
  const result = await promise;
  assert.deepEqual(result, { ideas: ["A"], run_id: "r1" });
});
