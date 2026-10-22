// node_modules/postgres/src/index.js
import os from "os";
import fs from "fs";

// node_modules/postgres/src/query.js
var originCache = /* @__PURE__ */ new Map();
var originStackCache = /* @__PURE__ */ new Map();
var originError = Symbol("OriginError");
var CLOSE = {};
var Query = class extends Promise {
  constructor(strings, args, handler, canceller, options = {}) {
    let resolve, reject;
    super((a, b2) => {
      resolve = a;
      reject = b2;
    });
    this.tagged = Array.isArray(strings.raw);
    this.strings = strings;
    this.args = args;
    this.handler = handler;
    this.canceller = canceller;
    this.options = options;
    this.state = null;
    this.statement = null;
    this.resolve = (x) => (this.active = false, resolve(x));
    this.reject = (x) => (this.active = false, reject(x));
    this.active = false;
    this.cancelled = null;
    this.executed = false;
    this.signature = "";
    this[originError] = this.handler.debug ? new Error() : this.tagged && cachedError(this.strings);
  }
  get origin() {
    return (this.handler.debug ? this[originError].stack : this.tagged && originStackCache.has(this.strings) ? originStackCache.get(this.strings) : originStackCache.set(this.strings, this[originError].stack).get(this.strings)) || "";
  }
  static get [Symbol.species]() {
    return Promise;
  }
  cancel() {
    return this.canceller && (this.canceller(this), this.canceller = null);
  }
  simple() {
    this.options.simple = true;
    this.options.prepare = false;
    return this;
  }
  async readable() {
    this.simple();
    this.streaming = true;
    return this;
  }
  async writable() {
    this.simple();
    this.streaming = true;
    return this;
  }
  cursor(rows = 1, fn) {
    this.options.simple = false;
    if (typeof rows === "function") {
      fn = rows;
      rows = 1;
    }
    this.cursorRows = rows;
    if (typeof fn === "function")
      return this.cursorFn = fn, this;
    let prev;
    return {
      [Symbol.asyncIterator]: () => ({
        next: () => {
          if (this.executed && !this.active)
            return { done: true };
          prev && prev();
          const promise = new Promise((resolve, reject) => {
            this.cursorFn = (value) => {
              resolve({ value, done: false });
              return new Promise((r) => prev = r);
            };
            this.resolve = () => (this.active = false, resolve({ done: true }));
            this.reject = (x) => (this.active = false, reject(x));
          });
          this.execute();
          return promise;
        },
        return() {
          prev && prev(CLOSE);
          return { done: true };
        }
      })
    };
  }
  describe() {
    this.options.simple = false;
    this.onlyDescribe = this.options.prepare = true;
    return this;
  }
  stream() {
    throw new Error(".stream has been renamed to .forEach");
  }
  forEach(fn) {
    this.forEachFn = fn;
    this.handle();
    return this;
  }
  raw() {
    this.isRaw = true;
    return this;
  }
  values() {
    this.isRaw = "values";
    return this;
  }
  async handle() {
    !this.executed && (this.executed = true) && await 1 && this.handler(this);
  }
  execute() {
    this.handle();
    return this;
  }
  then() {
    this.handle();
    return super.then.apply(this, arguments);
  }
  catch() {
    this.handle();
    return super.catch.apply(this, arguments);
  }
  finally() {
    this.handle();
    return super.finally.apply(this, arguments);
  }
};
function cachedError(xs) {
  if (originCache.has(xs))
    return originCache.get(xs);
  const x = Error.stackTraceLimit;
  Error.stackTraceLimit = 4;
  originCache.set(xs, new Error());
  Error.stackTraceLimit = x;
  return originCache.get(xs);
}

// node_modules/postgres/src/errors.js
var PostgresError = class extends Error {
  constructor(x) {
    super(x.message);
    this.name = this.constructor.name;
    Object.assign(this, x);
  }
};
var Errors = {
  connection,
  postgres,
  generic,
  notSupported
};
function connection(x, options, socket) {
  const { host, port } = socket || options;
  const error = Object.assign(
    new Error("write " + x + " " + (options.path || host + ":" + port)),
    {
      code: x,
      errno: x,
      address: options.path || host
    },
    options.path ? {} : { port }
  );
  Error.captureStackTrace(error, connection);
  return error;
}
function postgres(x) {
  const error = new PostgresError(x);
  Error.captureStackTrace(error, postgres);
  return error;
}
function generic(code, message) {
  const error = Object.assign(new Error(code + ": " + message), { code });
  Error.captureStackTrace(error, generic);
  return error;
}
function notSupported(x) {
  const error = Object.assign(
    new Error(x + " (B) is not supported"),
    {
      code: "MESSAGE_NOT_SUPPORTED",
      name: x
    }
  );
  Error.captureStackTrace(error, notSupported);
  return error;
}

// node_modules/postgres/src/types.js
var types = {
  string: {
    to: 25,
    from: null,
    // defaults to string
    serialize: (x) => "" + x
  },
  number: {
    to: 0,
    from: [21, 23, 26, 700, 701],
    serialize: (x) => "" + x,
    parse: (x) => +x
  },
  json: {
    to: 114,
    from: [114, 3802],
    serialize: (x) => JSON.stringify(x),
    parse: (x) => JSON.parse(x)
  },
  boolean: {
    to: 16,
    from: 16,
    serialize: (x) => x === true ? "t" : "f",
    parse: (x) => x === "t"
  },
  date: {
    to: 1184,
    from: [1082, 1114, 1184],
    serialize: (x) => (x instanceof Date ? x : new Date(x)).toISOString(),
    parse: (x) => new Date(x)
  },
  bytea: {
    to: 17,
    from: 17,
    serialize: (x) => "\\x" + Buffer.from(x).toString("hex"),
    parse: (x) => Buffer.from(x.slice(2), "hex")
  }
};
var NotTagged = class {
  then() {
    notTagged();
  }
  catch() {
    notTagged();
  }
  finally() {
    notTagged();
  }
};
var Identifier = class extends NotTagged {
  constructor(value) {
    super();
    this.value = escapeIdentifier(value);
  }
};
var Parameter = class extends NotTagged {
  constructor(value, type, array) {
    super();
    this.value = value;
    this.type = type;
    this.array = array;
  }
};
var Builder = class extends NotTagged {
  constructor(first, rest) {
    super();
    this.first = first;
    this.rest = rest;
  }
  build(before, parameters, types2, options) {
    const keyword = builders.map(([x, fn]) => ({ fn, i: before.search(x) })).sort((a, b2) => a.i - b2.i).pop();
    return keyword.i === -1 ? escapeIdentifiers(this.first, options) : keyword.fn(this.first, this.rest, parameters, types2, options);
  }
};
function handleValue(x, parameters, types2, options) {
  let value = x instanceof Parameter ? x.value : x;
  if (value === void 0) {
    x instanceof Parameter ? x.value = options.transform.undefined : value = x = options.transform.undefined;
    if (value === void 0)
      throw Errors.generic("UNDEFINED_VALUE", "Undefined values are not allowed");
  }
  return "$" + types2.push(
    x instanceof Parameter ? (parameters.push(x.value), x.array ? x.array[x.type || inferType(x.value)] || x.type || firstIsString(x.value) : x.type) : (parameters.push(x), inferType(x))
  );
}
var defaultHandlers = typeHandlers(types);
function stringify(q, string, value, parameters, types2, options) {
  for (let i = 1; i < q.strings.length; i++) {
    string += stringifyValue(string, value, parameters, types2, options) + q.strings[i];
    value = q.args[i];
  }
  return string;
}
function stringifyValue(string, value, parameters, types2, o) {
  return value instanceof Builder ? value.build(string, parameters, types2, o) : value instanceof Query ? fragment(value, parameters, types2, o) : value instanceof Identifier ? value.value : value && value[0] instanceof Query ? value.reduce((acc, x) => acc + " " + fragment(x, parameters, types2, o), "") : handleValue(value, parameters, types2, o);
}
function fragment(q, parameters, types2, options) {
  q.fragment = true;
  return stringify(q, q.strings[0], q.args[0], parameters, types2, options);
}
function valuesBuilder(first, parameters, types2, columns, options) {
  return first.map(
    (row) => "(" + columns.map(
      (column) => stringifyValue("values", row[column], parameters, types2, options)
    ).join(",") + ")"
  ).join(",");
}
function values(first, rest, parameters, types2, options) {
  const multi = Array.isArray(first[0]);
  const columns = rest.length ? rest.flat() : Object.keys(multi ? first[0] : first);
  return valuesBuilder(multi ? first : [first], parameters, types2, columns, options);
}
function select(first, rest, parameters, types2, options) {
  typeof first === "string" && (first = [first].concat(rest));
  if (Array.isArray(first))
    return escapeIdentifiers(first, options);
  let value;
  const columns = rest.length ? rest.flat() : Object.keys(first);
  return columns.map((x) => {
    value = first[x];
    return (value instanceof Query ? fragment(value, parameters, types2, options) : value instanceof Identifier ? value.value : handleValue(value, parameters, types2, options)) + " as " + escapeIdentifier(options.transform.column.to ? options.transform.column.to(x) : x);
  }).join(",");
}
var builders = Object.entries({
  values,
  in: (...xs) => {
    const x = values(...xs);
    return x === "()" ? "(null)" : x;
  },
  select,
  as: select,
  returning: select,
  "\\(": select,
  update(first, rest, parameters, types2, options) {
    return (rest.length ? rest.flat() : Object.keys(first)).map(
      (x) => escapeIdentifier(options.transform.column.to ? options.transform.column.to(x) : x) + "=" + stringifyValue("values", first[x], parameters, types2, options)
    );
  },
  insert(first, rest, parameters, types2, options) {
    const columns = rest.length ? rest.flat() : Object.keys(Array.isArray(first) ? first[0] : first);
    return "(" + escapeIdentifiers(columns, options) + ")values" + valuesBuilder(Array.isArray(first) ? first : [first], parameters, types2, columns, options);
  }
}).map(([x, fn]) => [new RegExp("((?:^|[\\s(])" + x + "(?:$|[\\s(]))(?![\\s\\S]*\\1)", "i"), fn]);
function notTagged() {
  throw Errors.generic("NOT_TAGGED_CALL", "Query not called as a tagged template literal");
}
var serializers = defaultHandlers.serializers;
var parsers = defaultHandlers.parsers;
function firstIsString(x) {
  if (Array.isArray(x))
    return firstIsString(x[0]);
  return typeof x === "string" ? 1009 : 0;
}
var mergeUserTypes = function(types2) {
  const user = typeHandlers(types2 || {});
  return {
    serializers: Object.assign({}, serializers, user.serializers),
    parsers: Object.assign({}, parsers, user.parsers)
  };
};
function typeHandlers(types2) {
  return Object.keys(types2).reduce((acc, k) => {
    types2[k].from && [].concat(types2[k].from).forEach((x) => acc.parsers[x] = types2[k].parse);
    if (types2[k].serialize) {
      acc.serializers[types2[k].to] = types2[k].serialize;
      types2[k].from && [].concat(types2[k].from).forEach((x) => acc.serializers[x] = types2[k].serialize);
    }
    return acc;
  }, { parsers: {}, serializers: {} });
}
function escapeIdentifiers(xs, { transform: { column } }) {
  return xs.map((x) => escapeIdentifier(column.to ? column.to(x) : x)).join(",");
}
var escapeIdentifier = function escape(str) {
  return '"' + str.replace(/"/g, '""').replace(/\./g, '"."') + '"';
};
var inferType = function inferType2(x) {
  return x instanceof Parameter ? x.type : x instanceof Date ? 1184 : x instanceof Uint8Array ? 17 : x === true || x === false ? 16 : typeof x === "bigint" ? 20 : Array.isArray(x) ? inferType2(x[0]) : 0;
};
var escapeBackslash = /\\/g;
var escapeQuote = /"/g;
function arrayEscape(x) {
  return x.replace(escapeBackslash, "\\\\").replace(escapeQuote, '\\"');
}
var arraySerializer = function arraySerializer2(xs, serializer, options, typarray) {
  if (Array.isArray(xs) === false)
    return xs;
  if (!xs.length)
    return "{}";
  const first = xs[0];
  const delimiter = typarray === 1020 ? ";" : ",";
  if (Array.isArray(first) && !first.type)
    return "{" + xs.map((x) => arraySerializer2(x, serializer, options, typarray)).join(delimiter) + "}";
  return "{" + xs.map((x) => {
    if (x === void 0) {
      x = options.transform.undefined;
      if (x === void 0)
        throw Errors.generic("UNDEFINED_VALUE", "Undefined values are not allowed");
    }
    return x === null ? "null" : '"' + arrayEscape(serializer ? serializer(x.type ? x.value : x) : "" + x) + '"';
  }).join(delimiter) + "}";
};
var arrayParserState = {
  i: 0,
  char: null,
  str: "",
  quoted: false,
  last: 0
};
var arrayParser = function arrayParser2(x, parser, typarray) {
  arrayParserState.i = arrayParserState.last = 0;
  return arrayParserLoop(arrayParserState, x, parser, typarray);
};
function arrayParserLoop(s, x, parser, typarray) {
  const xs = [];
  const delimiter = typarray === 1020 ? ";" : ",";
  for (; s.i < x.length; s.i++) {
    s.char = x[s.i];
    if (s.quoted) {
      if (s.char === "\\") {
        s.str += x[++s.i];
      } else if (s.char === '"') {
        xs.push(parser ? parser(s.str) : s.str);
        s.str = "";
        s.quoted = x[s.i + 1] === '"';
        s.last = s.i + 2;
      } else {
        s.str += s.char;
      }
    } else if (s.char === '"') {
      s.quoted = true;
    } else if (s.char === "{") {
      s.last = ++s.i;
      xs.push(arrayParserLoop(s, x, parser, typarray));
    } else if (s.char === "}") {
      s.quoted = false;
      s.last < s.i && xs.push(parser ? parser(x.slice(s.last, s.i)) : x.slice(s.last, s.i));
      s.last = s.i + 1;
      break;
    } else if (s.char === delimiter && s.p !== "}" && s.p !== '"') {
      xs.push(parser ? parser(x.slice(s.last, s.i)) : x.slice(s.last, s.i));
      s.last = s.i + 1;
    }
    s.p = s.char;
  }
  s.last < s.i && xs.push(parser ? parser(x.slice(s.last, s.i + 1)) : x.slice(s.last, s.i + 1));
  return xs;
}
var toCamel = (x) => {
  let str = x[0];
  for (let i = 1; i < x.length; i++)
    str += x[i] === "_" ? x[++i].toUpperCase() : x[i];
  return str;
};
var toPascal = (x) => {
  let str = x[0].toUpperCase();
  for (let i = 1; i < x.length; i++)
    str += x[i] === "_" ? x[++i].toUpperCase() : x[i];
  return str;
};
var toKebab = (x) => x.replace(/_/g, "-");
var fromCamel = (x) => x.replace(/([A-Z])/g, "_$1").toLowerCase();
var fromPascal = (x) => (x.slice(0, 1) + x.slice(1).replace(/([A-Z])/g, "_$1")).toLowerCase();
var fromKebab = (x) => x.replace(/-/g, "_");
function createJsonTransform(fn) {
  return function jsonTransform(x, column) {
    return typeof x === "object" && x !== null && (column.type === 114 || column.type === 3802) ? Array.isArray(x) ? x.map((x2) => jsonTransform(x2, column)) : Object.entries(x).reduce((acc, [k, v]) => Object.assign(acc, { [fn(k)]: jsonTransform(v, column) }), {}) : x;
  };
}
toCamel.column = { from: toCamel };
toCamel.value = { from: createJsonTransform(toCamel) };
fromCamel.column = { to: fromCamel };
var camel = { ...toCamel };
camel.column.to = fromCamel;
toPascal.column = { from: toPascal };
toPascal.value = { from: createJsonTransform(toPascal) };
fromPascal.column = { to: fromPascal };
var pascal = { ...toPascal };
pascal.column.to = fromPascal;
toKebab.column = { from: toKebab };
toKebab.value = { from: createJsonTransform(toKebab) };
fromKebab.column = { to: fromKebab };
var kebab = { ...toKebab };
kebab.column.to = fromKebab;

// node_modules/postgres/src/connection.js
import net from "net";
import tls from "tls";
import crypto from "crypto";
import Stream from "stream";
import { performance } from "perf_hooks";

// node_modules/postgres/src/result.js
var Result = class extends Array {
  constructor() {
    super();
    Object.defineProperties(this, {
      count: { value: null, writable: true },
      state: { value: null, writable: true },
      command: { value: null, writable: true },
      columns: { value: null, writable: true },
      statement: { value: null, writable: true }
    });
  }
  static get [Symbol.species]() {
    return Array;
  }
};

// node_modules/postgres/src/queue.js
var queue_default = Queue;
function Queue(initial = []) {
  let xs = initial.slice();
  let index = 0;
  return {
    get length() {
      return xs.length - index;
    },
    remove: (x) => {
      const index2 = xs.indexOf(x);
      return index2 === -1 ? null : (xs.splice(index2, 1), x);
    },
    push: (x) => (xs.push(x), x),
    shift: () => {
      const out = xs[index++];
      if (index === xs.length) {
        index = 0;
        xs = [];
      } else {
        xs[index - 1] = void 0;
      }
      return out;
    }
  };
}

// node_modules/postgres/src/bytes.js
var size = 256;
var buffer = Buffer.allocUnsafe(size);
var messages = "BCcDdEFfHPpQSX".split("").reduce((acc, x) => {
  const v = x.charCodeAt(0);
  acc[x] = () => {
    buffer[0] = v;
    b.i = 5;
    return b;
  };
  return acc;
}, {});
var b = Object.assign(reset, messages, {
  N: String.fromCharCode(0),
  i: 0,
  inc(x) {
    b.i += x;
    return b;
  },
  str(x) {
    const length = Buffer.byteLength(x);
    fit(length);
    b.i += buffer.write(x, b.i, length, "utf8");
    return b;
  },
  i16(x) {
    fit(2);
    buffer.writeUInt16BE(x, b.i);
    b.i += 2;
    return b;
  },
  i32(x, i) {
    if (i || i === 0) {
      buffer.writeUInt32BE(x, i);
      return b;
    }
    fit(4);
    buffer.writeUInt32BE(x, b.i);
    b.i += 4;
    return b;
  },
  z(x) {
    fit(x);
    buffer.fill(0, b.i, b.i + x);
    b.i += x;
    return b;
  },
  raw(x) {
    buffer = Buffer.concat([buffer.subarray(0, b.i), x]);
    b.i = buffer.length;
    return b;
  },
  end(at = 1) {
    buffer.writeUInt32BE(b.i - at, at);
    const out = buffer.subarray(0, b.i);
    b.i = 0;
    buffer = Buffer.allocUnsafe(size);
    return out;
  }
});
var bytes_default = b;
function fit(x) {
  if (buffer.length - b.i < x) {
    const prev = buffer, length = prev.length;
    buffer = Buffer.allocUnsafe(length + (length >> 1) + x);
    prev.copy(buffer);
  }
}
function reset() {
  b.i = 0;
  return b;
}

// node_modules/postgres/src/connection.js
var connection_default = Connection;
var uid = 1;
var Sync = bytes_default().S().end();
var Flush = bytes_default().H().end();
var SSLRequest = bytes_default().i32(8).i32(80877103).end(8);
var ExecuteUnnamed = Buffer.concat([bytes_default().E().str(bytes_default.N).i32(0).end(), Sync]);
var DescribeUnnamed = bytes_default().D().str("S").str(bytes_default.N).end();
var noop = () => {
};
var retryRoutines = /* @__PURE__ */ new Set([
  "FetchPreparedStatement",
  "RevalidateCachedQuery",
  "transformAssignedExpr"
]);
var errorFields = {
  83: "severity_local",
  // S
  86: "severity",
  // V
  67: "code",
  // C
  77: "message",
  // M
  68: "detail",
  // D
  72: "hint",
  // H
  80: "position",
  // P
  112: "internal_position",
  // p
  113: "internal_query",
  // q
  87: "where",
  // W
  115: "schema_name",
  // s
  116: "table_name",
  // t
  99: "column_name",
  // c
  100: "data type_name",
  // d
  110: "constraint_name",
  // n
  70: "file",
  // F
  76: "line",
  // L
  82: "routine"
  // R
};
function Connection(options, queues = {}, { onopen = noop, onend = noop, onclose = noop } = {}) {
  const {
    ssl,
    max,
    user,
    host,
    port,
    database,
    parsers: parsers2,
    transform,
    onnotice,
    onnotify,
    onparameter,
    max_pipeline,
    keep_alive,
    backoff: backoff2,
    target_session_attrs
  } = options;
  const sent = queue_default(), id = uid++, backend = { pid: null, secret: null }, idleTimer = timer(end, options.idle_timeout), lifeTimer = timer(end, options.max_lifetime), connectTimer = timer(connectTimedOut, options.connect_timeout);
  let socket = null, cancelMessage, result = new Result(), incoming = Buffer.alloc(0), needsTypes = options.fetch_types, backendParameters = {}, statements = {}, statementId = Math.random().toString(36).slice(2), statementCount = 1, closedDate = 0, remaining = 0, hostIndex = 0, retries = 0, length = 0, delay = 0, rows = 0, serverSignature = null, nextWriteTimer = null, terminated = false, incomings = null, results = null, initial = null, ending = null, stream = null, chunk = null, ended = null, nonce = null, query = null, final = null;
  const connection2 = {
    queue: queues.closed,
    idleTimer,
    connect(query2) {
      initial = query2;
      reconnect();
    },
    terminate,
    execute,
    cancel,
    end,
    count: 0,
    id
  };
  queues.closed && queues.closed.push(connection2);
  return connection2;
  async function createSocket() {
    let x;
    try {
      x = options.socket ? await Promise.resolve(options.socket(options)) : new net.Socket();
    } catch (e) {
      error(e);
      return;
    }
    x.on("error", error);
    x.on("close", closed);
    x.on("drain", drain);
    return x;
  }
  async function cancel({ pid, secret }, resolve, reject) {
    try {
      cancelMessage = bytes_default().i32(16).i32(80877102).i32(pid).i32(secret).end(16);
      await connect();
      socket.once("error", reject);
      socket.once("close", resolve);
    } catch (error2) {
      reject(error2);
    }
  }
  function execute(q) {
    if (terminated)
      return queryError(q, Errors.connection("CONNECTION_DESTROYED", options));
    if (q.cancelled)
      return;
    try {
      q.state = backend;
      query ? sent.push(q) : (query = q, query.active = true);
      build(q);
      return write(toBuffer(q)) && !q.describeFirst && !q.cursorFn && sent.length < max_pipeline && (!q.options.onexecute || q.options.onexecute(connection2));
    } catch (error2) {
      sent.length === 0 && write(Sync);
      errored(error2);
      return true;
    }
  }
  function toBuffer(q) {
    if (q.parameters.length >= 65534)
      throw Errors.generic("MAX_PARAMETERS_EXCEEDED", "Max number of parameters (65534) exceeded");
    return q.options.simple ? bytes_default().Q().str(q.statement.string + bytes_default.N).end() : q.describeFirst ? Buffer.concat([describe(q), Flush]) : q.prepare ? q.prepared ? prepared(q) : Buffer.concat([describe(q), prepared(q)]) : unnamed(q);
  }
  function describe(q) {
    return Buffer.concat([
      Parse(q.statement.string, q.parameters, q.statement.types, q.statement.name),
      Describe("S", q.statement.name)
    ]);
  }
  function prepared(q) {
    return Buffer.concat([
      Bind(q.parameters, q.statement.types, q.statement.name, q.cursorName),
      q.cursorFn ? Execute("", q.cursorRows) : ExecuteUnnamed
    ]);
  }
  function unnamed(q) {
    return Buffer.concat([
      Parse(q.statement.string, q.parameters, q.statement.types),
      DescribeUnnamed,
      prepared(q)
    ]);
  }
  function build(q) {
    const parameters = [], types2 = [];
    const string = stringify(q, q.strings[0], q.args[0], parameters, types2, options);
    !q.tagged && q.args.forEach((x) => handleValue(x, parameters, types2, options));
    q.prepare = options.prepare && ("prepare" in q.options ? q.options.prepare : true);
    q.string = string;
    q.signature = q.prepare && types2 + string;
    q.onlyDescribe && delete statements[q.signature];
    q.parameters = q.parameters || parameters;
    q.prepared = q.prepare && q.signature in statements;
    q.describeFirst = q.onlyDescribe || parameters.length && !q.prepared;
    q.statement = q.prepared ? statements[q.signature] : { string, types: types2, name: q.prepare ? statementId + statementCount++ : "" };
    typeof options.debug === "function" && options.debug(id, string, parameters, types2);
  }
  function write(x, fn) {
    chunk = chunk ? Buffer.concat([chunk, x]) : Buffer.from(x);
    if (fn || chunk.length >= 1024)
      return nextWrite(fn);
    nextWriteTimer === null && (nextWriteTimer = setImmediate(nextWrite));
    return true;
  }
  function nextWrite(fn) {
    const x = socket.write(chunk, fn);
    nextWriteTimer !== null && clearImmediate(nextWriteTimer);
    chunk = nextWriteTimer = null;
    return x;
  }
  function connectTimedOut() {
    errored(Errors.connection("CONNECT_TIMEOUT", options, socket));
    socket.destroy();
  }
  async function secure() {
    write(SSLRequest);
    const canSSL = await new Promise((r) => socket.once("data", (x) => r(x[0] === 83)));
    if (!canSSL && ssl === "prefer")
      return connected();
    socket.removeAllListeners();
    socket = tls.connect({
      socket,
      servername: net.isIP(socket.host) ? void 0 : socket.host,
      ...ssl === "require" || ssl === "allow" || ssl === "prefer" ? { rejectUnauthorized: false } : ssl === "verify-full" ? {} : typeof ssl === "object" ? ssl : {}
    });
    socket.on("secureConnect", connected);
    socket.on("error", error);
    socket.on("close", closed);
    socket.on("drain", drain);
  }
  function drain() {
    !query && onopen(connection2);
  }
  function data(x) {
    if (incomings) {
      incomings.push(x);
      remaining -= x.length;
      if (remaining > 0)
        return;
    }
    incoming = incomings ? Buffer.concat(incomings, length - remaining) : incoming.length === 0 ? x : Buffer.concat([incoming, x], incoming.length + x.length);
    while (incoming.length > 4) {
      length = incoming.readUInt32BE(1);
      if (length >= incoming.length) {
        remaining = length - incoming.length;
        incomings = [incoming];
        break;
      }
      try {
        handle(incoming.subarray(0, length + 1));
      } catch (e) {
        query && (query.cursorFn || query.describeFirst) && write(Sync);
        errored(e);
      }
      incoming = incoming.subarray(length + 1);
      remaining = 0;
      incomings = null;
    }
  }
  async function connect() {
    terminated = false;
    backendParameters = {};
    socket || (socket = await createSocket());
    if (!socket)
      return;
    connectTimer.start();
    if (options.socket)
      return ssl ? secure() : connected();
    socket.on("connect", ssl ? secure : connected);
    if (options.path)
      return socket.connect(options.path);
    socket.ssl = ssl;
    socket.connect(port[hostIndex], host[hostIndex]);
    socket.host = host[hostIndex];
    socket.port = port[hostIndex];
    hostIndex = (hostIndex + 1) % port.length;
  }
  function reconnect() {
    setTimeout(connect, closedDate ? closedDate + delay - performance.now() : 0);
  }
  function connected() {
    try {
      statements = {};
      needsTypes = options.fetch_types;
      statementId = Math.random().toString(36).slice(2);
      statementCount = 1;
      lifeTimer.start();
      socket.on("data", data);
      keep_alive && socket.setKeepAlive && socket.setKeepAlive(true, 1e3 * keep_alive);
      const s = StartupMessage();
      write(s);
    } catch (err) {
      error(err);
    }
  }
  function error(err) {
    if (connection2.queue === queues.connecting && options.host[retries + 1])
      return;
    errored(err);
    while (sent.length)
      queryError(sent.shift(), err);
  }
  function errored(err) {
    stream && (stream.destroy(err), stream = null);
    query && queryError(query, err);
    initial && (queryError(initial, err), initial = null);
  }
  function queryError(query2, err) {
    if (query2.reserve)
      return query2.reject(err);
    if (!err || typeof err !== "object")
      err = new Error(err);
    "query" in err || "parameters" in err || Object.defineProperties(err, {
      stack: { value: err.stack + query2.origin.replace(/.*\n/, "\n"), enumerable: options.debug },
      query: { value: query2.string, enumerable: options.debug },
      parameters: { value: query2.parameters, enumerable: options.debug },
      args: { value: query2.args, enumerable: options.debug },
      types: { value: query2.statement && query2.statement.types, enumerable: options.debug }
    });
    query2.reject(err);
  }
  function end() {
    return ending || (!connection2.reserved && onend(connection2), !connection2.reserved && !initial && !query && sent.length === 0 ? (terminate(), new Promise((r) => socket && socket.readyState !== "closed" ? socket.once("close", r) : r())) : ending = new Promise((r) => ended = r));
  }
  function terminate() {
    terminated = true;
    if (stream || query || initial || sent.length)
      error(Errors.connection("CONNECTION_DESTROYED", options));
    clearImmediate(nextWriteTimer);
    if (socket) {
      socket.removeListener("data", data);
      socket.removeListener("connect", connected);
      socket.readyState === "open" && socket.end(bytes_default().X().end());
    }
    ended && (ended(), ending = ended = null);
  }
  async function closed(hadError) {
    incoming = Buffer.alloc(0);
    remaining = 0;
    incomings = null;
    clearImmediate(nextWriteTimer);
    socket.removeListener("data", data);
    socket.removeListener("connect", connected);
    idleTimer.cancel();
    lifeTimer.cancel();
    connectTimer.cancel();
    socket.removeAllListeners();
    socket = null;
    if (initial)
      return reconnect();
    !hadError && (query || sent.length) && error(Errors.connection("CONNECTION_CLOSED", options, socket));
    closedDate = performance.now();
    hadError && options.shared.retries++;
    delay = (typeof backoff2 === "function" ? backoff2(options.shared.retries) : backoff2) * 1e3;
    onclose(connection2, Errors.connection("CONNECTION_CLOSED", options, socket));
  }
  function handle(xs, x = xs[0]) {
    (x === 68 ? DataRow : (
      // D
      x === 100 ? CopyData : (
        // d
        x === 65 ? NotificationResponse : (
          // A
          x === 83 ? ParameterStatus : (
            // S
            x === 90 ? ReadyForQuery : (
              // Z
              x === 67 ? CommandComplete : (
                // C
                x === 50 ? BindComplete : (
                  // 2
                  x === 49 ? ParseComplete : (
                    // 1
                    x === 116 ? ParameterDescription : (
                      // t
                      x === 84 ? RowDescription : (
                        // T
                        x === 82 ? Authentication : (
                          // R
                          x === 110 ? NoData : (
                            // n
                            x === 75 ? BackendKeyData : (
                              // K
                              x === 69 ? ErrorResponse : (
                                // E
                                x === 115 ? PortalSuspended : (
                                  // s
                                  x === 51 ? CloseComplete : (
                                    // 3
                                    x === 71 ? CopyInResponse : (
                                      // G
                                      x === 78 ? NoticeResponse : (
                                        // N
                                        x === 72 ? CopyOutResponse : (
                                          // H
                                          x === 99 ? CopyDone : (
                                            // c
                                            x === 73 ? EmptyQueryResponse : (
                                              // I
                                              x === 86 ? FunctionCallResponse : (
                                                // V
                                                x === 118 ? NegotiateProtocolVersion : (
                                                  // v
                                                  x === 87 ? CopyBothResponse : (
                                                    // W
                                                    /* c8 ignore next */
                                                    UnknownMessage
                                                  )
                                                )
                                              )
                                            )
                                          )
                                        )
                                      )
                                    )
                                  )
                                )
                              )
                            )
                          )
                        )
                      )
                    )
                  )
                )
              )
            )
          )
        )
      )
    ))(xs);
  }
  function DataRow(x) {
    let index = 7;
    let length2;
    let column;
    let value;
    const row = query.isRaw ? new Array(query.statement.columns.length) : {};
    for (let i = 0; i < query.statement.columns.length; i++) {
      column = query.statement.columns[i];
      length2 = x.readInt32BE(index);
      index += 4;
      value = length2 === -1 ? null : query.isRaw === true ? x.subarray(index, index += length2) : column.parser === void 0 ? x.toString("utf8", index, index += length2) : column.parser.array === true ? column.parser(x.toString("utf8", index + 1, index += length2)) : column.parser(x.toString("utf8", index, index += length2));
      query.isRaw ? row[i] = query.isRaw === true ? value : transform.value.from ? transform.value.from(value, column) : value : row[column.name] = transform.value.from ? transform.value.from(value, column) : value;
    }
    query.forEachFn ? query.forEachFn(transform.row.from ? transform.row.from(row) : row, result) : result[rows++] = transform.row.from ? transform.row.from(row) : row;
  }
  function ParameterStatus(x) {
    const [k, v] = x.toString("utf8", 5, x.length - 1).split(bytes_default.N);
    backendParameters[k] = v;
    if (options.parameters[k] !== v) {
      options.parameters[k] = v;
      onparameter && onparameter(k, v);
    }
  }
  function ReadyForQuery(x) {
    query && query.options.simple && query.resolve(results || result);
    query = results = null;
    result = new Result();
    connectTimer.cancel();
    if (initial) {
      if (target_session_attrs) {
        if (!backendParameters.in_hot_standby || !backendParameters.default_transaction_read_only)
          return fetchState();
        else if (tryNext(target_session_attrs, backendParameters))
          return terminate();
      }
      if (needsTypes) {
        initial.reserve && (initial = null);
        return fetchArrayTypes();
      }
      initial && !initial.reserve && execute(initial);
      options.shared.retries = retries = 0;
      initial = null;
      return;
    }
    while (sent.length && (query = sent.shift()) && (query.active = true, query.cancelled))
      Connection(options).cancel(query.state, query.cancelled.resolve, query.cancelled.reject);
    if (query)
      return;
    connection2.reserved ? !connection2.reserved.release && x[5] === 73 ? ending ? terminate() : (connection2.reserved = null, onopen(connection2)) : connection2.reserved() : ending ? terminate() : onopen(connection2);
  }
  function CommandComplete(x) {
    rows = 0;
    for (let i = x.length - 1; i > 0; i--) {
      if (x[i] === 32 && x[i + 1] < 58 && result.count === null)
        result.count = +x.toString("utf8", i + 1, x.length - 1);
      if (x[i - 1] >= 65) {
        result.command = x.toString("utf8", 5, i);
        result.state = backend;
        break;
      }
    }
    final && (final(), final = null);
    if (result.command === "BEGIN" && max !== 1 && !connection2.reserved)
      return errored(Errors.generic("UNSAFE_TRANSACTION", "Only use sql.begin, sql.reserved or max: 1"));
    if (query.options.simple)
      return BindComplete();
    if (query.cursorFn) {
      result.count && query.cursorFn(result);
      write(Sync);
    }
    query.resolve(result);
  }
  function ParseComplete() {
    query.parsing = false;
  }
  function BindComplete() {
    !result.statement && (result.statement = query.statement);
    result.columns = query.statement.columns;
  }
  function ParameterDescription(x) {
    const length2 = x.readUInt16BE(5);
    for (let i = 0; i < length2; ++i)
      !query.statement.types[i] && (query.statement.types[i] = x.readUInt32BE(7 + i * 4));
    query.prepare && (statements[query.signature] = query.statement);
    query.describeFirst && !query.onlyDescribe && (write(prepared(query)), query.describeFirst = false);
  }
  function RowDescription(x) {
    if (result.command) {
      results = results || [result];
      results.push(result = new Result());
      result.count = null;
      query.statement.columns = null;
    }
    const length2 = x.readUInt16BE(5);
    let index = 7;
    let start;
    query.statement.columns = Array(length2);
    for (let i = 0; i < length2; ++i) {
      start = index;
      while (x[index++] !== 0) ;
      const table = x.readUInt32BE(index);
      const number = x.readUInt16BE(index + 4);
      const type = x.readUInt32BE(index + 6);
      query.statement.columns[i] = {
        name: transform.column.from ? transform.column.from(x.toString("utf8", start, index - 1)) : x.toString("utf8", start, index - 1),
        parser: parsers2[type],
        table,
        number,
        type
      };
      index += 18;
    }
    result.statement = query.statement;
    if (query.onlyDescribe)
      return query.resolve(query.statement), write(Sync);
  }
  async function Authentication(x, type = x.readUInt32BE(5)) {
    (type === 3 ? AuthenticationCleartextPassword : type === 5 ? AuthenticationMD5Password : type === 10 ? SASL : type === 11 ? SASLContinue : type === 12 ? SASLFinal : type !== 0 ? UnknownAuth : noop)(x, type);
  }
  async function AuthenticationCleartextPassword() {
    const payload = await Pass();
    write(
      bytes_default().p().str(payload).z(1).end()
    );
  }
  async function AuthenticationMD5Password(x) {
    const payload = "md5" + await md5(
      Buffer.concat([
        Buffer.from(await md5(await Pass() + user)),
        x.subarray(9)
      ])
    );
    write(
      bytes_default().p().str(payload).z(1).end()
    );
  }
  async function SASL() {
    nonce = (await crypto.randomBytes(18)).toString("base64");
    bytes_default().p().str("SCRAM-SHA-256" + bytes_default.N);
    const i = bytes_default.i;
    write(bytes_default.inc(4).str("n,,n=*,r=" + nonce).i32(bytes_default.i - i - 4, i).end());
  }
  async function SASLContinue(x) {
    const res = x.toString("utf8", 9).split(",").reduce((acc, x2) => (acc[x2[0]] = x2.slice(2), acc), {});
    const saltedPassword = await crypto.pbkdf2Sync(
      await Pass(),
      Buffer.from(res.s, "base64"),
      parseInt(res.i),
      32,
      "sha256"
    );
    const clientKey = await hmac(saltedPassword, "Client Key");
    const auth = "n=*,r=" + nonce + ",r=" + res.r + ",s=" + res.s + ",i=" + res.i + ",c=biws,r=" + res.r;
    serverSignature = (await hmac(await hmac(saltedPassword, "Server Key"), auth)).toString("base64");
    const payload = "c=biws,r=" + res.r + ",p=" + xor(
      clientKey,
      Buffer.from(await hmac(await sha256(clientKey), auth))
    ).toString("base64");
    write(
      bytes_default().p().str(payload).end()
    );
  }
  function SASLFinal(x) {
    if (x.toString("utf8", 9).split(bytes_default.N, 1)[0].slice(2) === serverSignature)
      return;
    errored(Errors.generic("SASL_SIGNATURE_MISMATCH", "The server did not return the correct signature"));
    socket.destroy();
  }
  function Pass() {
    return Promise.resolve(
      typeof options.pass === "function" ? options.pass() : options.pass
    );
  }
  function NoData() {
    result.statement = query.statement;
    result.statement.columns = [];
    if (query.onlyDescribe)
      return query.resolve(query.statement), write(Sync);
  }
  function BackendKeyData(x) {
    backend.pid = x.readUInt32BE(5);
    backend.secret = x.readUInt32BE(9);
  }
  async function fetchArrayTypes() {
    needsTypes = false;
    const types2 = await new Query([`
      select b.oid, b.typarray
      from pg_catalog.pg_type a
      left join pg_catalog.pg_type b on b.oid = a.typelem
      where a.typcategory = 'A'
      group by b.oid, b.typarray
      order by b.oid
    `], [], execute);
    types2.forEach(({ oid, typarray }) => addArrayType(oid, typarray));
  }
  function addArrayType(oid, typarray) {
    if (!!options.parsers[typarray] && !!options.serializers[typarray]) return;
    const parser = options.parsers[oid];
    options.shared.typeArrayMap[oid] = typarray;
    options.parsers[typarray] = (xs) => arrayParser(xs, parser, typarray);
    options.parsers[typarray].array = true;
    options.serializers[typarray] = (xs) => arraySerializer(xs, options.serializers[oid], options, typarray);
  }
  function tryNext(x, xs) {
    return x === "read-write" && xs.default_transaction_read_only === "on" || x === "read-only" && xs.default_transaction_read_only === "off" || x === "primary" && xs.in_hot_standby === "on" || x === "standby" && xs.in_hot_standby === "off" || x === "prefer-standby" && xs.in_hot_standby === "off" && options.host[retries];
  }
  function fetchState() {
    const query2 = new Query([`
      show transaction_read_only;
      select pg_catalog.pg_is_in_recovery()
    `], [], execute, null, { simple: true });
    query2.resolve = ([[a], [b2]]) => {
      backendParameters.default_transaction_read_only = a.transaction_read_only;
      backendParameters.in_hot_standby = b2.pg_is_in_recovery ? "on" : "off";
    };
    query2.execute();
  }
  function ErrorResponse(x) {
    query && (query.cursorFn || query.describeFirst) && write(Sync);
    const error2 = Errors.postgres(parseError(x));
    query && query.retried ? errored(query.retried) : query && query.prepared && retryRoutines.has(error2.routine) ? retry(query, error2) : errored(error2);
  }
  function retry(q, error2) {
    delete statements[q.signature];
    q.retried = error2;
    execute(q);
  }
  function NotificationResponse(x) {
    if (!onnotify)
      return;
    let index = 9;
    while (x[index++] !== 0) ;
    onnotify(
      x.toString("utf8", 9, index - 1),
      x.toString("utf8", index, x.length - 1)
    );
  }
  async function PortalSuspended() {
    try {
      const x = await Promise.resolve(query.cursorFn(result));
      rows = 0;
      x === CLOSE ? write(Close(query.portal)) : (result = new Result(), write(Execute("", query.cursorRows)));
    } catch (err) {
      write(Sync);
      query.reject(err);
    }
  }
  function CloseComplete() {
    result.count && query.cursorFn(result);
    query.resolve(result);
  }
  function CopyInResponse() {
    stream = new Stream.Writable({
      autoDestroy: true,
      write(chunk2, encoding, callback) {
        socket.write(bytes_default().d().raw(chunk2).end(), callback);
      },
      destroy(error2, callback) {
        callback(error2);
        socket.write(bytes_default().f().str(error2 + bytes_default.N).end());
        stream = null;
      },
      final(callback) {
        socket.write(bytes_default().c().end());
        final = callback;
      }
    });
    query.resolve(stream);
  }
  function CopyOutResponse() {
    stream = new Stream.Readable({
      read() {
        socket.resume();
      }
    });
    query.resolve(stream);
  }
  function CopyBothResponse() {
    stream = new Stream.Duplex({
      autoDestroy: true,
      read() {
        socket.resume();
      },
      /* c8 ignore next 11 */
      write(chunk2, encoding, callback) {
        socket.write(bytes_default().d().raw(chunk2).end(), callback);
      },
      destroy(error2, callback) {
        callback(error2);
        socket.write(bytes_default().f().str(error2 + bytes_default.N).end());
        stream = null;
      },
      final(callback) {
        socket.write(bytes_default().c().end());
        final = callback;
      }
    });
    query.resolve(stream);
  }
  function CopyData(x) {
    stream && (stream.push(x.subarray(5)) || socket.pause());
  }
  function CopyDone() {
    stream && stream.push(null);
    stream = null;
  }
  function NoticeResponse(x) {
    onnotice ? onnotice(parseError(x)) : console.log(parseError(x));
  }
  function EmptyQueryResponse() {
  }
  function FunctionCallResponse() {
    errored(Errors.notSupported("FunctionCallResponse"));
  }
  function NegotiateProtocolVersion() {
    errored(Errors.notSupported("NegotiateProtocolVersion"));
  }
  function UnknownMessage(x) {
    console.error("Postgres.js : Unknown Message:", x[0]);
  }
  function UnknownAuth(x, type) {
    console.error("Postgres.js : Unknown Auth:", type);
  }
  function Bind(parameters, types2, statement = "", portal = "") {
    let prev, type;
    bytes_default().B().str(portal + bytes_default.N).str(statement + bytes_default.N).i16(0).i16(parameters.length);
    parameters.forEach((x, i) => {
      if (x === null)
        return bytes_default.i32(4294967295);
      type = types2[i];
      parameters[i] = x = type in options.serializers ? options.serializers[type](x) : "" + x;
      prev = bytes_default.i;
      bytes_default.inc(4).str(x).i32(bytes_default.i - prev - 4, prev);
    });
    bytes_default.i16(0);
    return bytes_default.end();
  }
  function Parse(str, parameters, types2, name = "") {
    bytes_default().P().str(name + bytes_default.N).str(str + bytes_default.N).i16(parameters.length);
    parameters.forEach((x, i) => bytes_default.i32(types2[i] || 0));
    return bytes_default.end();
  }
  function Describe(x, name = "") {
    return bytes_default().D().str(x).str(name + bytes_default.N).end();
  }
  function Execute(portal = "", rows2 = 0) {
    return Buffer.concat([
      bytes_default().E().str(portal + bytes_default.N).i32(rows2).end(),
      Flush
    ]);
  }
  function Close(portal = "") {
    return Buffer.concat([
      bytes_default().C().str("P").str(portal + bytes_default.N).end(),
      bytes_default().S().end()
    ]);
  }
  function StartupMessage() {
    return cancelMessage || bytes_default().inc(4).i16(3).z(2).str(
      Object.entries(Object.assign(
        {
          user,
          database,
          client_encoding: "UTF8"
        },
        options.connection
      )).filter(([, v]) => v).map(([k, v]) => k + bytes_default.N + v).join(bytes_default.N)
    ).z(2).end(0);
  }
}
function parseError(x) {
  const error = {};
  let start = 5;
  for (let i = 5; i < x.length - 1; i++) {
    if (x[i] === 0) {
      error[errorFields[x[start]]] = x.toString("utf8", start + 1, i);
      start = i + 1;
    }
  }
  return error;
}
function md5(x) {
  return crypto.createHash("md5").update(x).digest("hex");
}
function hmac(key, x) {
  return crypto.createHmac("sha256", key).update(x).digest();
}
function sha256(x) {
  return crypto.createHash("sha256").update(x).digest();
}
function xor(a, b2) {
  const length = Math.max(a.length, b2.length);
  const buffer2 = Buffer.allocUnsafe(length);
  for (let i = 0; i < length; i++)
    buffer2[i] = a[i] ^ b2[i];
  return buffer2;
}
function timer(fn, seconds) {
  seconds = typeof seconds === "function" ? seconds() : seconds;
  if (!seconds)
    return { cancel: noop, start: noop };
  let timer2;
  return {
    cancel() {
      timer2 && (clearTimeout(timer2), timer2 = null);
    },
    start() {
      timer2 && clearTimeout(timer2);
      timer2 = setTimeout(done, seconds * 1e3, arguments);
    }
  };
  function done(args) {
    fn.apply(null, args);
    timer2 = null;
  }
}

// node_modules/postgres/src/subscribe.js
var noop2 = () => {
};
function Subscribe(postgres2, options) {
  const subscribers = /* @__PURE__ */ new Map(), slot = "postgresjs_" + Math.random().toString(36).slice(2), state = {};
  let connection2, stream, ended = false;
  const sql2 = subscribe.sql = postgres2({
    ...options,
    transform: { column: {}, value: {}, row: {} },
    max: 1,
    fetch_types: false,
    idle_timeout: null,
    max_lifetime: null,
    connection: {
      ...options.connection,
      replication: "database"
    },
    onclose: async function() {
      if (ended)
        return;
      stream = null;
      state.pid = state.secret = void 0;
      connected(await init(sql2, slot, options.publications));
      subscribers.forEach((event) => event.forEach(({ onsubscribe }) => onsubscribe()));
    },
    no_subscribe: true
  });
  const end = sql2.end, close = sql2.close;
  sql2.end = async () => {
    ended = true;
    stream && await new Promise((r) => (stream.once("close", r), stream.end()));
    return end();
  };
  sql2.close = async () => {
    stream && await new Promise((r) => (stream.once("close", r), stream.end()));
    return close();
  };
  return subscribe;
  async function subscribe(event, fn, onsubscribe = noop2, onerror = noop2) {
    event = parseEvent(event);
    if (!connection2)
      connection2 = init(sql2, slot, options.publications);
    const subscriber = { fn, onsubscribe };
    const fns = subscribers.has(event) ? subscribers.get(event).add(subscriber) : subscribers.set(event, /* @__PURE__ */ new Set([subscriber])).get(event);
    const unsubscribe = () => {
      fns.delete(subscriber);
      fns.size === 0 && subscribers.delete(event);
    };
    return connection2.then((x) => {
      connected(x);
      onsubscribe();
      stream && stream.on("error", onerror);
      return { unsubscribe, state, sql: sql2 };
    });
  }
  function connected(x) {
    stream = x.stream;
    state.pid = x.state.pid;
    state.secret = x.state.secret;
  }
  async function init(sql3, slot2, publications) {
    if (!publications)
      throw new Error("Missing publication names");
    const xs = await sql3.unsafe(
      `CREATE_REPLICATION_SLOT ${slot2} TEMPORARY LOGICAL pgoutput NOEXPORT_SNAPSHOT`
    );
    const [x] = xs;
    const stream2 = await sql3.unsafe(
      `START_REPLICATION SLOT ${slot2} LOGICAL ${x.consistent_point} (proto_version '1', publication_names '${publications}')`
    ).writable();
    const state2 = {
      lsn: Buffer.concat(x.consistent_point.split("/").map((x2) => Buffer.from(("00000000" + x2).slice(-8), "hex")))
    };
    stream2.on("data", data);
    stream2.on("error", error);
    stream2.on("close", sql3.close);
    return { stream: stream2, state: xs.state };
    function error(e) {
      console.error("Unexpected error during logical streaming - reconnecting", e);
    }
    function data(x2) {
      if (x2[0] === 119) {
        parse(x2.subarray(25), state2, sql3.options.parsers, handle, options.transform);
      } else if (x2[0] === 107 && x2[17]) {
        state2.lsn = x2.subarray(1, 9);
        pong();
      }
    }
    function handle(a, b2) {
      const path = b2.relation.schema + "." + b2.relation.table;
      call("*", a, b2);
      call("*:" + path, a, b2);
      b2.relation.keys.length && call("*:" + path + "=" + b2.relation.keys.map((x2) => a[x2.name]), a, b2);
      call(b2.command, a, b2);
      call(b2.command + ":" + path, a, b2);
      b2.relation.keys.length && call(b2.command + ":" + path + "=" + b2.relation.keys.map((x2) => a[x2.name]), a, b2);
    }
    function pong() {
      const x2 = Buffer.alloc(34);
      x2[0] = "r".charCodeAt(0);
      x2.fill(state2.lsn, 1);
      x2.writeBigInt64BE(BigInt(Date.now() - Date.UTC(2e3, 0, 1)) * BigInt(1e3), 25);
      stream2.write(x2);
    }
  }
  function call(x, a, b2) {
    subscribers.has(x) && subscribers.get(x).forEach(({ fn }) => fn(a, b2, x));
  }
}
function Time(x) {
  return new Date(Date.UTC(2e3, 0, 1) + Number(x / BigInt(1e3)));
}
function parse(x, state, parsers2, handle, transform) {
  const char = (acc, [k, v]) => (acc[k.charCodeAt(0)] = v, acc);
  Object.entries({
    R: (x2) => {
      let i = 1;
      const r = state[x2.readUInt32BE(i)] = {
        schema: x2.toString("utf8", i += 4, i = x2.indexOf(0, i)) || "pg_catalog",
        table: x2.toString("utf8", i + 1, i = x2.indexOf(0, i + 1)),
        columns: Array(x2.readUInt16BE(i += 2)),
        keys: []
      };
      i += 2;
      let columnIndex = 0, column;
      while (i < x2.length) {
        column = r.columns[columnIndex++] = {
          key: x2[i++],
          name: transform.column.from ? transform.column.from(x2.toString("utf8", i, i = x2.indexOf(0, i))) : x2.toString("utf8", i, i = x2.indexOf(0, i)),
          type: x2.readUInt32BE(i += 1),
          parser: parsers2[x2.readUInt32BE(i)],
          atttypmod: x2.readUInt32BE(i += 4)
        };
        column.key && r.keys.push(column);
        i += 4;
      }
    },
    Y: () => {
    },
    // Type
    O: () => {
    },
    // Origin
    B: (x2) => {
      state.date = Time(x2.readBigInt64BE(9));
      state.lsn = x2.subarray(1, 9);
    },
    I: (x2) => {
      let i = 1;
      const relation = state[x2.readUInt32BE(i)];
      const { row } = tuples(x2, relation.columns, i += 7, transform);
      handle(row, {
        command: "insert",
        relation
      });
    },
    D: (x2) => {
      let i = 1;
      const relation = state[x2.readUInt32BE(i)];
      i += 4;
      const key = x2[i] === 75;
      handle(
        key || x2[i] === 79 ? tuples(x2, relation.columns, i += 3, transform).row : null,
        {
          command: "delete",
          relation,
          key
        }
      );
    },
    U: (x2) => {
      let i = 1;
      const relation = state[x2.readUInt32BE(i)];
      i += 4;
      const key = x2[i] === 75;
      const xs = key || x2[i] === 79 ? tuples(x2, relation.columns, i += 3, transform) : null;
      xs && (i = xs.i);
      const { row } = tuples(x2, relation.columns, i + 3, transform);
      handle(row, {
        command: "update",
        relation,
        key,
        old: xs && xs.row
      });
    },
    T: () => {
    },
    // Truncate,
    C: () => {
    }
    // Commit
  }).reduce(char, {})[x[0]](x);
}
function tuples(x, columns, xi, transform) {
  let type, column, value;
  const row = transform.raw ? new Array(columns.length) : {};
  for (let i = 0; i < columns.length; i++) {
    type = x[xi++];
    column = columns[i];
    value = type === 110 ? null : type === 117 ? void 0 : column.parser === void 0 ? x.toString("utf8", xi + 4, xi += 4 + x.readUInt32BE(xi)) : column.parser.array === true ? column.parser(x.toString("utf8", xi + 5, xi += 4 + x.readUInt32BE(xi))) : column.parser(x.toString("utf8", xi + 4, xi += 4 + x.readUInt32BE(xi)));
    transform.raw ? row[i] = transform.raw === true ? value : transform.value.from ? transform.value.from(value, column) : value : row[column.name] = transform.value.from ? transform.value.from(value, column) : value;
  }
  return { i: xi, row: transform.row.from ? transform.row.from(row) : row };
}
function parseEvent(x) {
  const xs = x.match(/^(\*|insert|update|delete)?:?([^.]+?\.?[^=]+)?=?(.+)?/i) || [];
  if (!xs)
    throw new Error("Malformed subscribe pattern: " + x);
  const [, command, path, key] = xs;
  return (command || "*") + (path ? ":" + (path.indexOf(".") === -1 ? "public." + path : path) : "") + (key ? "=" + key : "");
}

// node_modules/postgres/src/large.js
import Stream2 from "stream";
function largeObject(sql2, oid, mode = 131072 | 262144) {
  return new Promise(async (resolve, reject) => {
    await sql2.begin(async (sql3) => {
      let finish;
      !oid && ([{ oid }] = await sql3`select lo_creat(-1) as oid`);
      const [{ fd }] = await sql3`select lo_open(${oid}, ${mode}) as fd`;
      const lo = {
        writable,
        readable,
        close: () => sql3`select lo_close(${fd})`.then(finish),
        tell: () => sql3`select lo_tell64(${fd})`,
        read: (x) => sql3`select loread(${fd}, ${x}) as data`,
        write: (x) => sql3`select lowrite(${fd}, ${x})`,
        truncate: (x) => sql3`select lo_truncate64(${fd}, ${x})`,
        seek: (x, whence = 0) => sql3`select lo_lseek64(${fd}, ${x}, ${whence})`,
        size: () => sql3`
          select
            lo_lseek64(${fd}, location, 0) as position,
            seek.size
          from (
            select
              lo_lseek64($1, 0, 2) as size,
              tell.location
            from (select lo_tell64($1) as location) tell
          ) seek
        `
      };
      resolve(lo);
      return new Promise(async (r) => finish = r);
      async function readable({
        highWaterMark = 2048 * 8,
        start = 0,
        end = Infinity
      } = {}) {
        let max = end - start;
        start && await lo.seek(start);
        return new Stream2.Readable({
          highWaterMark,
          async read(size2) {
            const l = size2 > max ? size2 - max : size2;
            max -= size2;
            const [{ data }] = await lo.read(l);
            this.push(data);
            if (data.length < size2)
              this.push(null);
          }
        });
      }
      async function writable({
        highWaterMark = 2048 * 8,
        start = 0
      } = {}) {
        start && await lo.seek(start);
        return new Stream2.Writable({
          highWaterMark,
          write(chunk, encoding, callback) {
            lo.write(chunk).then(() => callback(), callback);
          }
        });
      }
    }).catch(reject);
  });
}

// node_modules/postgres/src/index.js
Object.assign(Postgres, {
  PostgresError,
  toPascal,
  pascal,
  toCamel,
  camel,
  toKebab,
  kebab,
  fromPascal,
  fromCamel,
  fromKebab,
  BigInt: {
    to: 20,
    from: [20],
    parse: (x) => BigInt(x),
    // eslint-disable-line
    serialize: (x) => x.toString()
  }
});
var src_default = Postgres;
function Postgres(a, b2) {
  const options = parseOptions(a, b2), subscribe = options.no_subscribe || Subscribe(Postgres, { ...options });
  let ending = false;
  const queries = queue_default(), connecting = queue_default(), reserved = queue_default(), closed = queue_default(), ended = queue_default(), open = queue_default(), busy = queue_default(), full = queue_default(), queues = { connecting, reserved, closed, ended, open, busy, full };
  const connections = [...Array(options.max)].map(() => connection_default(options, queues, { onopen, onend, onclose }));
  const sql2 = Sql(handler);
  Object.assign(sql2, {
    get parameters() {
      return options.parameters;
    },
    largeObject: largeObject.bind(null, sql2),
    subscribe,
    CLOSE,
    END: CLOSE,
    PostgresError,
    options,
    reserve,
    listen,
    begin,
    close,
    end
  });
  return sql2;
  function Sql(handler2) {
    handler2.debug = options.debug;
    Object.entries(options.types).reduce((acc, [name, type]) => {
      acc[name] = (x) => new Parameter(x, type.to);
      return acc;
    }, typed);
    Object.assign(sql3, {
      types: typed,
      typed,
      unsafe,
      notify,
      array,
      json: json2,
      file
    });
    return sql3;
    function typed(value, type) {
      return new Parameter(value, type);
    }
    function sql3(strings, ...args) {
      const query = strings && Array.isArray(strings.raw) ? new Query(strings, args, handler2, cancel) : typeof strings === "string" && !args.length ? new Identifier(options.transform.column.to ? options.transform.column.to(strings) : strings) : new Builder(strings, args);
      return query;
    }
    function unsafe(string, args = [], options2 = {}) {
      arguments.length === 2 && !Array.isArray(args) && (options2 = args, args = []);
      const query = new Query([string], args, handler2, cancel, {
        prepare: false,
        ...options2,
        simple: "simple" in options2 ? options2.simple : args.length === 0
      });
      return query;
    }
    function file(path, args = [], options2 = {}) {
      arguments.length === 2 && !Array.isArray(args) && (options2 = args, args = []);
      const query = new Query([], args, (query2) => {
        fs.readFile(path, "utf8", (err, string) => {
          if (err)
            return query2.reject(err);
          query2.strings = [string];
          handler2(query2);
        });
      }, cancel, {
        ...options2,
        simple: "simple" in options2 ? options2.simple : args.length === 0
      });
      return query;
    }
  }
  async function listen(name, fn, onlisten) {
    const listener = { fn, onlisten };
    const sql3 = listen.sql || (listen.sql = Postgres({
      ...options,
      max: 1,
      idle_timeout: null,
      max_lifetime: null,
      fetch_types: false,
      onclose() {
        Object.entries(listen.channels).forEach(([name2, { listeners }]) => {
          delete listen.channels[name2];
          Promise.all(listeners.map((l) => listen(name2, l.fn, l.onlisten).catch(() => {
          })));
        });
      },
      onnotify(c, x) {
        c in listen.channels && listen.channels[c].listeners.forEach((l) => l.fn(x));
      }
    }));
    const channels = listen.channels || (listen.channels = {}), exists = name in channels;
    if (exists) {
      channels[name].listeners.push(listener);
      const result2 = await channels[name].result;
      listener.onlisten && listener.onlisten();
      return { state: result2.state, unlisten };
    }
    channels[name] = { result: sql3`listen ${sql3.unsafe('"' + name.replace(/"/g, '""') + '"')}`, listeners: [listener] };
    const result = await channels[name].result;
    listener.onlisten && listener.onlisten();
    return { state: result.state, unlisten };
    async function unlisten() {
      if (name in channels === false)
        return;
      channels[name].listeners = channels[name].listeners.filter((x) => x !== listener);
      if (channels[name].listeners.length)
        return;
      delete channels[name];
      return sql3`unlisten ${sql3.unsafe('"' + name.replace(/"/g, '""') + '"')}`;
    }
  }
  async function notify(channel, payload) {
    return await sql2`select pg_notify(${channel}, ${"" + payload})`;
  }
  async function reserve() {
    const queue = queue_default();
    const c = open.length ? open.shift() : await new Promise((resolve, reject) => {
      const query = { reserve: resolve, reject };
      queries.push(query);
      closed.length && connect(closed.shift(), query);
    });
    move(c, reserved);
    c.reserved = () => queue.length ? c.execute(queue.shift()) : move(c, reserved);
    c.reserved.release = true;
    const sql3 = Sql(handler2);
    sql3.release = () => {
      c.reserved = null;
      onopen(c);
    };
    return sql3;
    function handler2(q) {
      c.queue === full ? queue.push(q) : c.execute(q) || move(c, full);
    }
  }
  async function begin(options2, fn) {
    !fn && (fn = options2, options2 = "");
    const queries2 = queue_default();
    let savepoints = 0, connection2, prepare = null;
    try {
      await sql2.unsafe("begin " + options2.replace(/[^a-z ]/ig, ""), [], { onexecute }).execute();
      return await Promise.race([
        scope(connection2, fn),
        new Promise((_, reject) => connection2.onclose = reject)
      ]);
    } catch (error) {
      throw error;
    }
    async function scope(c, fn2, name) {
      const sql3 = Sql(handler2);
      sql3.savepoint = savepoint;
      sql3.prepare = (x) => prepare = x.replace(/[^a-z0-9$-_. ]/gi);
      let uncaughtError, result;
      name && await sql3`savepoint ${sql3(name)}`;
      try {
        result = await new Promise((resolve, reject) => {
          const x = fn2(sql3);
          Promise.resolve(Array.isArray(x) ? Promise.all(x) : x).then(resolve, reject);
        });
        if (uncaughtError)
          throw uncaughtError;
      } catch (e) {
        await (name ? sql3`rollback to ${sql3(name)}` : sql3`rollback`);
        throw e instanceof PostgresError && e.code === "25P02" && uncaughtError || e;
      }
      if (!name) {
        prepare ? await sql3`prepare transaction '${sql3.unsafe(prepare)}'` : await sql3`commit`;
      }
      return result;
      function savepoint(name2, fn3) {
        if (name2 && Array.isArray(name2.raw))
          return savepoint((sql4) => sql4.apply(sql4, arguments));
        arguments.length === 1 && (fn3 = name2, name2 = null);
        return scope(c, fn3, "s" + savepoints++ + (name2 ? "_" + name2 : ""));
      }
      function handler2(q) {
        q.catch((e) => uncaughtError || (uncaughtError = e));
        c.queue === full ? queries2.push(q) : c.execute(q) || move(c, full);
      }
    }
    function onexecute(c) {
      connection2 = c;
      move(c, reserved);
      c.reserved = () => queries2.length ? c.execute(queries2.shift()) : move(c, reserved);
    }
  }
  function move(c, queue) {
    c.queue.remove(c);
    queue.push(c);
    c.queue = queue;
    queue === open ? c.idleTimer.start() : c.idleTimer.cancel();
    return c;
  }
  function json2(x) {
    return new Parameter(x, 3802);
  }
  function array(x, type) {
    if (!Array.isArray(x))
      return array(Array.from(arguments));
    return new Parameter(x, type || (x.length ? inferType(x) || 25 : 0), options.shared.typeArrayMap);
  }
  function handler(query) {
    if (ending)
      return query.reject(Errors.connection("CONNECTION_ENDED", options, options));
    if (open.length)
      return go(open.shift(), query);
    if (closed.length)
      return connect(closed.shift(), query);
    busy.length ? go(busy.shift(), query) : queries.push(query);
  }
  function go(c, query) {
    return c.execute(query) ? move(c, busy) : move(c, full);
  }
  function cancel(query) {
    return new Promise((resolve, reject) => {
      query.state ? query.active ? connection_default(options).cancel(query.state, resolve, reject) : query.cancelled = { resolve, reject } : (queries.remove(query), query.cancelled = true, query.reject(Errors.generic("57014", "canceling statement due to user request")), resolve());
    });
  }
  async function end({ timeout = null } = {}) {
    if (ending)
      return ending;
    await 1;
    let timer2;
    return ending = Promise.race([
      new Promise((r) => timeout !== null && (timer2 = setTimeout(destroy, timeout * 1e3, r))),
      Promise.all(connections.map((c) => c.end()).concat(
        listen.sql ? listen.sql.end({ timeout: 0 }) : [],
        subscribe.sql ? subscribe.sql.end({ timeout: 0 }) : []
      ))
    ]).then(() => clearTimeout(timer2));
  }
  async function close() {
    await Promise.all(connections.map((c) => c.end()));
  }
  async function destroy(resolve) {
    await Promise.all(connections.map((c) => c.terminate()));
    while (queries.length)
      queries.shift().reject(Errors.connection("CONNECTION_DESTROYED", options));
    resolve();
  }
  function connect(c, query) {
    move(c, connecting);
    c.connect(query);
    return c;
  }
  function onend(c) {
    move(c, ended);
  }
  function onopen(c) {
    if (queries.length === 0)
      return move(c, open);
    let max = Math.ceil(queries.length / (connecting.length + 1)), ready = true;
    while (ready && queries.length && max-- > 0) {
      const query = queries.shift();
      if (query.reserve)
        return query.reserve(c);
      ready = c.execute(query);
    }
    ready ? move(c, busy) : move(c, full);
  }
  function onclose(c, e) {
    move(c, closed);
    c.reserved = null;
    c.onclose && (c.onclose(e), c.onclose = null);
    options.onclose && options.onclose(c.id);
    queries.length && connect(c, queries.shift());
  }
}
function parseOptions(a, b2) {
  if (a && a.shared)
    return a;
  const env = process.env, o = (!a || typeof a === "string" ? b2 : a) || {}, { url, multihost } = parseUrl(a), query = [...url.searchParams].reduce((a2, [b3, c]) => (a2[b3] = c, a2), {}), host = o.hostname || o.host || multihost || url.hostname || env.PGHOST || "localhost", port = o.port || url.port || env.PGPORT || 5432, user = o.user || o.username || url.username || env.PGUSERNAME || env.PGUSER || osUsername();
  o.no_prepare && (o.prepare = false);
  query.sslmode && (query.ssl = query.sslmode, delete query.sslmode);
  "timeout" in o && (console.log("The timeout option is deprecated, use idle_timeout instead"), o.idle_timeout = o.timeout);
  query.sslrootcert === "system" && (query.ssl = "verify-full");
  const ints = ["idle_timeout", "connect_timeout", "max_lifetime", "max_pipeline", "backoff", "keep_alive"];
  const defaults = {
    max: 10,
    ssl: false,
    idle_timeout: null,
    connect_timeout: 30,
    max_lifetime,
    max_pipeline: 100,
    backoff,
    keep_alive: 60,
    prepare: true,
    debug: false,
    fetch_types: true,
    publications: "alltables",
    target_session_attrs: null
  };
  return {
    host: Array.isArray(host) ? host : host.split(",").map((x) => x.split(":")[0]),
    port: Array.isArray(port) ? port : host.split(",").map((x) => parseInt(x.split(":")[1] || port)),
    path: o.path || host.indexOf("/") > -1 && host + "/.s.PGSQL." + port,
    database: o.database || o.db || (url.pathname || "").slice(1) || env.PGDATABASE || user,
    user,
    pass: o.pass || o.password || url.password || env.PGPASSWORD || "",
    ...Object.entries(defaults).reduce(
      (acc, [k, d]) => {
        const value = k in o ? o[k] : k in query ? query[k] === "disable" || query[k] === "false" ? false : query[k] : env["PG" + k.toUpperCase()] || d;
        acc[k] = typeof value === "string" && ints.includes(k) ? +value : value;
        return acc;
      },
      {}
    ),
    connection: {
      application_name: env.PGAPPNAME || "postgres.js",
      ...o.connection,
      ...Object.entries(query).reduce((acc, [k, v]) => (k in defaults || (acc[k] = v), acc), {})
    },
    types: o.types || {},
    target_session_attrs: tsa(o, url, env),
    onnotice: o.onnotice,
    onnotify: o.onnotify,
    onclose: o.onclose,
    onparameter: o.onparameter,
    socket: o.socket,
    transform: parseTransform(o.transform || { undefined: void 0 }),
    parameters: {},
    shared: { retries: 0, typeArrayMap: {} },
    ...mergeUserTypes(o.types)
  };
}
function tsa(o, url, env) {
  const x = o.target_session_attrs || url.searchParams.get("target_session_attrs") || env.PGTARGETSESSIONATTRS;
  if (!x || ["read-write", "read-only", "primary", "standby", "prefer-standby"].includes(x))
    return x;
  throw new Error("target_session_attrs " + x + " is not supported");
}
function backoff(retries) {
  return (0.5 + Math.random() / 2) * Math.min(3 ** retries / 100, 20);
}
function max_lifetime() {
  return 60 * (30 + Math.random() * 30);
}
function parseTransform(x) {
  return {
    undefined: x.undefined,
    column: {
      from: typeof x.column === "function" ? x.column : x.column && x.column.from,
      to: x.column && x.column.to
    },
    value: {
      from: typeof x.value === "function" ? x.value : x.value && x.value.from,
      to: x.value && x.value.to
    },
    row: {
      from: typeof x.row === "function" ? x.row : x.row && x.row.from,
      to: x.row && x.row.to
    }
  };
}
function parseUrl(url) {
  if (!url || typeof url !== "string")
    return { url: { searchParams: /* @__PURE__ */ new Map() } };
  let host = url;
  host = host.slice(host.indexOf("://") + 3).split(/[?/]/)[0];
  host = decodeURIComponent(host.slice(host.indexOf("@") + 1));
  const urlObj = new URL(url.replace(host, host.split(",")[0]));
  return {
    url: {
      username: decodeURIComponent(urlObj.username),
      password: decodeURIComponent(urlObj.password),
      host: urlObj.host,
      hostname: urlObj.hostname,
      port: urlObj.port,
      pathname: urlObj.pathname,
      searchParams: urlObj.searchParams
    },
    multihost: host.indexOf(",") > -1 && host
  };
}
function osUsername() {
  try {
    return os.userInfo().username;
  } catch (_) {
    return process.env.USERNAME || process.env.USER || process.env.LOGNAME;
  }
}

// migration/free-stack/live/index.mjs
var sql = src_default(process.env.DATABASE_URL, {
  max: 3,
  idle_timeout: 20,
  connect_timeout: 6,
  prepare: false,
  transform: { undefined: null }
});
var origins = /* @__PURE__ */ new Set(["https://mrxpronos.github.io", "http://localhost:3000", "http://127.0.0.1:3000"]);
var num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
function headers(request) {
  const origin = request.headers.get("origin") || "";
  const h = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "vary": "Origin" };
  if (origins.has(origin)) h["access-control-allow-origin"] = origin;
  return h;
}
function json(req, body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: headers(req) });
}
var safeDate = (date) => /^\d{4}-\d{2}-\d{2}$/.test(date) && !Number.isNaN(Date.parse(date + "T00:00:00Z"));
var freshness = (value) => Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 1e3));
function prediction(p) {
  const threshold = num(p.threshold);
  const prob = num(p.probability);
  return {
    id: p.id,
    type: p.prediction_type,
    title: p.prediction_type,
    badge: p.signal_tier || "",
    color: "",
    probability: prob,
    message: p.message,
    threshold,
    pronostic: threshold,
    current: p.current_value,
    signal_value: p.signal_value ?? p.current_value,
    projected: p.projected_value,
    projected_value: p.projected_value,
    reliability: Math.round(num(p.reliability_score, prob * 100)),
    model_fair_odds: p.model_fair_odds,
    bookmaker_odds: p.bookmaker_odds,
    implied_probability: p.implied_probability,
    edge: p.edge,
    expected_value: p.expected_value,
    value_score: p.value_score,
    data_quality_score: p.data_quality_score,
    freshness_seconds: p.freshness_seconds,
    source_count: p.source_count,
    source_confidence: p.source_confidence,
    source_agreement_score: p.source_agreement_score,
    signal_tier: p.signal_tier,
    pricing_mode: p.pricing_mode,
    line_candidate_count: p.line_candidate_count,
    line_candidate_rank: p.line_candidate_rank,
    baseline_threshold: p.baseline_threshold,
    historical_uplift_cap: p.historical_uplift_cap,
    selected_uplift: p.selected_uplift,
    model_version: p.model_version,
    final_value: p.final_value,
    headroom: p.headroom,
    reasons: [],
    confidence: p.confidence,
    validated: !!p.validated,
    outcome: p.outcome,
    validation_type: p.validation_type,
    created_at: p.created_at,
    signal_home_score: p.signal_home_score,
    signal_away_score: p.signal_away_score,
    signal_minute: p.signal_minute,
    signal_half1_home: p.signal_half1_home,
    signal_half1_away: p.signal_half1_away,
    signal_half2_home: p.signal_half2_home,
    signal_half2_away: p.signal_half2_away,
    home_score: p.signal_home_score,
    away_score: p.signal_away_score,
    minute: p.signal_minute,
    live_odds: p.live_odds,
    stake_fcfa: p.stake_fcfa,
    potential_gain_fcfa: p.potential_gain_fcfa,
    odds_source: p.odds_source
  };
}
async function currentMatches() {
  const rows = await sql`SELECT id,raw_data,updated_at FROM public.matches_live
   WHERE updated_at >= now()-INTERVAL '900 seconds' ORDER BY updated_at DESC LIMIT 150`;
  if (!rows.length) return [];
  const ids = rows.map((x) => String(x.id));
  const pp = await sql`SELECT id,match_id,prediction_type,probability,message,threshold,current_value,projected_value,
   signal_value,reliability_score,model_fair_odds,bookmaker_odds,implied_probability,edge,expected_value,
   value_score,data_quality_score,freshness_seconds,source_count,source_confidence,source_agreement_score,
   signal_tier,pricing_mode,line_candidate_count,line_candidate_rank,baseline_threshold,historical_uplift_cap,
   selected_uplift,model_version,final_value,headroom,confidence,validated,outcome,validation_type,created_at,
   signal_home_score,signal_away_score,signal_minute,signal_half1_home,signal_half1_away,signal_half2_home,
   signal_half2_away,live_odds,stake_fcfa,potential_gain_fcfa,odds_source
   FROM public.live_predictions WHERE match_id=ANY(${sql.array(ids)}) AND validated=false
   ORDER BY created_at DESC LIMIT 1000`;
  const byId = /* @__PURE__ */ new Map();
  for (const p of pp) {
    const k = String(p.match_id);
    if (!byId.has(k)) byId.set(k, []);
    byId.get(k).push(prediction(p));
  }
  return rows.map((row) => {
    const base = row.raw_data && typeof row.raw_data === "object" ? row.raw_data : {};
    const preds = (byId.get(String(row.id)) || []).sort((a, b2) => num(b2.value_score) - num(a.value_score));
    return {
      ...base,
      id: String(row.id),
      league: { name: base.league?.name || base.league_name || 'Football' },
      predictions: preds,
      all_predictions: preds,
      events: [],
      freshness_seconds: freshness(row.updated_at),
      updated_at: row.updated_at
    };
  });
}
async function predictionHistory() {
  const rows = await sql`SELECT id,match_id,match_name,home_team,away_team,home_score,away_score,minute,league_name,
 prediction_type,probability,message,threshold,current_value,projected_value,confidence,validated,outcome,
 created_at,validated_at,validation_type,signal_value,reliability_score,model_fair_odds,bookmaker_odds,
 implied_probability,edge,expected_value,value_score,data_quality_score,freshness_seconds,source_count,
 source_confidence,signal_tier,pricing_mode,line_candidate_count,line_candidate_rank,baseline_threshold,
 historical_uplift_cap,selected_uplift,model_version,final_value,headroom,signal_home_score,signal_away_score,
 signal_minute,signal_half1_home,signal_half1_away,signal_half2_home,signal_half2_away,live_odds,stake_fcfa,
 potential_gain_fcfa,odds_source FROM public.live_predictions WHERE created_at >= now()-INTERVAL '48 hours'
 ORDER BY created_at DESC LIMIT 350`;
  const lookupIds=[...new Set(rows.map(p=>String(p.match_id)).filter(Boolean))];
  let matchLogos=new Map();
  if(lookupIds.length){
    try{
      const logos=await sql`SELECT id,raw_data->>'home_logo' AS home_logo,
        raw_data->>'away_logo' AS away_logo,raw_data->>'league_logo' AS league_logo
        FROM public.matches_live WHERE id=ANY(${sql.array(lookupIds)})`;
      matchLogos=new Map(logos.map(x=>[String(x.id),x]));
    }catch(e){console.error("NEON_LIVE_HISTORY_LOGO_LOOKUP_FAILED",e?.code||e?.name);}
  }
  return rows.map((p) => ({
    ...prediction(p),
    home_logo:matchLogos.get(String(p.match_id))?.home_logo||null,
    away_logo:matchLogos.get(String(p.match_id))?.away_logo||null,
    league_logo:matchLogos.get(String(p.match_id))?.league_logo||null,
    match_id: String(p.match_id),
    home_team: p.home_team,
    away_team: p.away_team,
    current_minute: p.minute,
    league: { name: p.league_name },
    match: p.match_name,
    home_score: p.signal_home_score ?? p.home_score ?? 0,
    away_score: p.signal_away_score ?? p.away_score ?? 0,
    minute: p.signal_minute ?? p.minute ?? null,
    validated_at: p.validated_at,
    timestamp: Date.parse(p.created_at)
  }));
}
async function scheduled() {
  const rows = await sql`SELECT fixture,updated_at,event_date FROM public.live_scheduled_fixtures
   WHERE event_date BETWEEN now()-INTERVAL '10 minutes' AND now()+INTERVAL '48 hours'
   AND updated_at >= now()-INTERVAL '45 minutes' ORDER BY event_date LIMIT 150`;
  return rows.map((x) => ({...x.fixture,league:{name:x.fixture?.league?.name || x.fixture?.league_name || 'Football'}})).filter((x) => x && !x.is_live && !x.is_finished);
}
var index_default = {
  async fetch(req) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/^\/functions\/v1\/live/, "").replace(/\/$/, "") || "/";
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: { ...headers(req), "access-control-allow-methods": "GET,OPTIONS", "access-control-allow-headers": "content-type,authorization,apikey,x-cron-secret" } });
    if (req.method !== "GET") return json(req, { error: "refresh_engine_not_migrated", service: "neon-live-readonly" }, 503);
    try {
      if (path === "/" || path === "/health") {
        const rows = await sql`SELECT (SELECT count(*)::integer FROM public.live_predictions) AS prediction_count,
      (SELECT max(updated_at) FROM public.matches_live) AS latest_match_update`;
        return json(req, { ok: true, service: "neon-live", engine: "neon-espn-safe-v1", prediction_count: rows[0].prediction_count, latest_match_update: rows[0].latest_match_update });
      }
      if (path === "/matches") return json(req, { matches: await currentMatches() });
      if (path === "/opportunities") {
        const matches = await currentMatches();
        const out = matches.filter((x) => x.predictions.length).sort((a, b2) => num(b2.predictions[0].value_score) - num(a.predictions[0].value_score));
        return json(req, { opportunities: out.slice(0, 12) });
      }
      if (path === "/today") {
        const date = url.searchParams.get("date") || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
        if (!safeDate(date)) return json(req, { error: "invalid_date" }, 400);
        const live = await currentMatches();
        const future = await scheduled();
        return json(req, {
          data: { live: { count: live.length, matches: live }, scheduled: { count: future.length, matches: future }, finished: { count: 0, matches: [] } },
          meta: { source: "neon-live-staging", bsd_calls: 0, upstream_espn_calls: 0, refresh_engine: "neon-espn-safe-v1" }
        });
      }
      if (path === "/predictions/history") return json(req, { history: await predictionHistory() });
      if (path === "/predictions/by-id") {
        const id = url.searchParams.get("id") || "";
        if (!/^[0-9a-f-]{36}$/i.test(id)) return json(req, { error: "invalid_id" }, 400);
        const history = await sql`SELECT id FROM public.live_predictions WHERE id=${id}::uuid LIMIT 1`;
        if (!history.length) return json(req, { error: "not_found" }, 404);
        const pp = await predictionHistory();
        const found = pp.find((x) => x.id === id);
        return found ? json(req, { prediction: found }) : json(req, { error: "outside_history_window" }, 404);
      }
      if (path === "/daily/today") {
        const date = url.searchParams.get("date") || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
        if (!safeDate(date)) return json(req, { error: "invalid_date" }, 400);
        const pp = await sql`SELECT * FROM public.daily_predictions WHERE prediction_date=${date}::date ORDER BY kickoff LIMIT 150`;
        return json(req, { date, predictions: pp, count: pp.length, source: "daily_predictions", snapshot_available: pp.length > 0 });
      }
      return json(req, { error: "not_found" }, 404);
    } catch (e) {
      console.error("NEON_LIVE_READ_ERROR", e?.code || e?.name);
      return json(req, { error: "database_unavailable", service: "neon-live-readonly" }, 503);
    }
  }
};
export {
  index_default as default
};

{
// MrXPRONOS: Neon LIVE bounded refresh, isolated from Telegram.
// Runs only after verifying a GitHub Actions OIDC token.
// Intentionally DOES NOT generate betting signals or invoke Telegram.
const NEON_REFRESH_AUD = "mrxpronos-neon-live-refresh-20261022";
const ALLOWED_REPO = "MrXPRONOS/MrXPRONOS_App";
const ALLOWED_REF = "refs/heads/migration/supabase-to-free-stack-20261022";
const EXPECTED_WORKFLOW = ALLOWED_REPO + "/.github/workflows/neon-live-refresh-test.yml@" + ALLOWED_REF;
const ESPN_ORIGIN = "https://site.api.espn.com/apis/site/v2/sports/soccer/";

function decodeJwtPart(part) {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8"));
}
async function verifyGithubOidc(req) {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ") || auth.length > 9000) return false;
  const token = auth.slice(7);
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  let hdr, claims;
  try {
    hdr = decodeJwtPart(parts[0]); claims = decodeJwtPart(parts[1]);
  } catch { return false; }
  const now = Math.floor(Date.now() / 1000);
  if (hdr.alg !== "RS256" || !hdr.kid || !claims ||
      claims.iss !== "https://token.actions.githubusercontent.com" ||
      claims.aud !== NEON_REFRESH_AUD ||
      claims.repository !== ALLOWED_REPO ||
      !((claims.ref === ALLOWED_REF && claims.workflow_ref === EXPECTED_WORKFLOW) || (claims.ref === "refs/heads/main" && claims.workflow_ref === ALLOWED_REPO + "/.github/workflows/neon-live-refresh.yml@refs/heads/main")) ||
      claims.event_name !== "push" && claims.event_name !== "workflow_dispatch" && claims.event_name !== "schedule" ||
      !(Number(claims.iat) <= now + 60) || !(Number(claims.exp) > now) ||
      Number(claims.exp) > now + 7200) return false;
  try {
    const res = await fetch("https://token.actions.githubusercontent.com/.well-known/jwks", {
      headers: { Accept: "application/json" }, signal: AbortSignal.timeout(7000)
    });
    if (!res.ok) return false;
    const jwks = await res.json();
    const jwk = jwks.keys?.find(k => k.kid === hdr.kid && k.kty === "RSA" && k.use === "sig");
    if (!jwk) return false;
    const key = await crypto.subtle.importKey("jwk", jwk, {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"}, false, ["verify"]);
    return await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,
      Buffer.from(parts[2],"base64url"),Buffer.from(parts[0]+"."+parts[1]));
  } catch(e) {
    console.error("NEON_OIDC_VERIFICATION_FAILED",String(e?.name || "error"));
    return false;
  }
}
function asNumber(val) {
  if (val === null || val === undefined || val === "" || val === "-") return null;
  const n=Number(String(val).replace(/%$/,"").replace(",","."));
  return Number.isFinite(n) ? n : null;
}
function firstGood(...values) {
  for (const v of values) if (v !== null && v !== undefined && v !== "") return v;
  return null;
}
function normalizeStatsList(stats) {
  const result={};
  const map={
    corners:"corner_kicks",cornerkicks:"corner_kicks",totalcorners:"corner_kicks",
    woncorners:"corner_kicks",cornerswon:"corner_kicks",
    totalshots:"total_shots",shots:"total_shots",shotattempts:"total_shots",
    shotsongoal:"shots_on_target",shotsontarget:"shots_on_target",
    foul:"fouls",fouls:"fouls",foulscommitted:"fouls",
    possession:"ball_possession",possessionpct:"ball_possession"
  };
  for (const s of Array.isArray(stats)?stats:[]) {
    const raw=String(s?.name || s?.abbreviation || s?.label || s?.type || "").toLowerCase().replace(/[^a-z]/g,"");
    const key=map[raw];
    const num=asNumber(firstGood(s?.value,s?.displayValue,s?.stat));
    if (key && num!==null && num>=0 && num<10000) result[key]=num;
  }
  return result;
}
function fromTeams(teams, homeId, awayId) {
  let result={home:{},away:{}};
  for(const side of Array.isArray(teams)?teams:[]) {
    const id=String(side?.team?.id ?? "");
    const role=String(side?.homeAway ?? "");
    let key=id&&id===homeId?"home":id&&id===awayId?"away":role==="home"?"home":role==="away"?"away":null;
    if (key) result[key]=normalizeStatsList(side?.statistics);
  }
  return result;
}
function mergeStats(base,more) {
  return {home:{...(base?.home||{}),...(more?.home||{})},away:{...(base?.away||{}),...(more?.away||{})}};
}
function buildLiveStats(parts) {
  const home=parts.home||{},away=parts.away||{};
  const totals={};
  for(const [field,totalField] of [["corner_kicks","corners"],["total_shots","total_shots"],["shots_on_target","shots_on_target"],["fouls","fouls"]]){
    if(Number.isFinite(home[field])&&Number.isFinite(away[field]))totals[totalField]=home[field]+away[field];
  }
  return {home,away,totals};
}
function parseEvent(event, sourceLeague) {
  if(!/^\d{1,16}$/.test(String(event?.id??"")))return null;
  const contest=event?.competitions?.[0]||{};
  const competitors=contest.competitors||[];
  const home=competitors.find(x=>x.homeAway==="home"),away=competitors.find(x=>x.homeAway==="away");
  if(!home?.team||!away?.team)return null;
  const homeName=String(home.team.displayName||home.team.name||"").trim().slice(0,200);
  const awayName=String(away.team.displayName||away.team.name||"").trim().slice(0,200);
  if(homeName.length<2||awayName.length<2)return null;
  const dt=Date.parse(event.date||contest.date||"");
  if(!Number.isFinite(dt))return null;
  const state=event?.status?.type?.state||contest?.status?.type?.state||"";
  const finished=state==="post"||event.status?.type?.completed===true;
  const clock=String(event.status?.displayClock||contest.status?.displayClock||event.status?.type?.detail||"");
  const minute=firstGood(asNumber(clock.match(/^\d+/)?.[0]),asNumber(event.status?.period),0);
  const timeNow=Date.now();
  const isLive=state==="in"&&!finished&&dt>timeNow-6*3600000&&dt<timeNow+3600000;
  const isScheduled=state==="pre"&&dt>=timeNow-10*60000&&dt<timeNow+48*3600000;
  if(!isLive&&!isScheduled)return null;
  return {
    id:"espn:"+event.id, provider_id:String(event.id),
    home_team:homeName,away_team:awayName,
    home_team_id:String(home.team.id||""),away_team_id:String(away.team.id||""),
    home_logo:home.team.logo||"",away_logo:away.team.logo||"",
    home_score:Math.max(0,Math.trunc(asNumber(home.score)||0)),
    away_score:Math.max(0,Math.trunc(asNumber(away.score)||0)),
    current_minute:Math.max(0,Math.min(150,Math.trunc(asNumber(minute)||0))),
    event_date:new Date(dt).toISOString(),
    league_name:String(event?.league?.name||contest?.notes?.[0]?.headline||sourceLeague||"Football").slice(0,200),
    status:isLive?"inprogress":"notstarted",
    period:event.status?.type?.description||"",
    is_live:isLive,is_finished:false,
    stats_sources:[],live_stats:{home:{},away:{},totals:{}},
    _scoreboard_stats:fromTeams(competitors,String(home.team.id||""),String(away.team.id||""))
  };
}
async function getEspn(path) {
  const res=await fetch(ESPN_ORIGIN+path,{
    headers:{"Accept":"application/json","User-Agent":"MrXPRONOS/2.0 (+football statistics)"},
    signal:AbortSignal.timeout(9500)
  });
  if(!res.ok)throw new Error("ESPN_HTTP_"+res.status);
  if(!(res.headers.get("content-type")||"").includes("json"))throw new Error("ESPN_NOT_JSON");
  return res.json();
}
async function fetchFromESPN() {
  const now=new Date();
  const dates=[now.toISOString().slice(0,10).replace(/-/g,"")];
  if(now.getUTCHours()<7)dates.unshift(new Date(Date.now()-86400000).toISOString().slice(0,10).replace(/-/g,""));
  const paths=dates.map(d=>"all/scoreboard?dates="+d+"&limit=500");
  // Regional sources supported by the existing MrXPRONOS code. Kept bounded.
  paths.push("conmebol.sudamericana/scoreboard?dates="+dates[dates.length-1]+"&limit=100");
  const upstream=await Promise.allSettled(paths.map(p=>getEspn(p)));
  const events=new Map(), failures=[];
  upstream.forEach((result,i)=>{
    if(result.status!=="fulfilled"){failures.push({source:paths[i].split("/")[0],error:String(result.reason?.message||"network").slice(0,90)});return;}
    const body=result.value;
    if(!Array.isArray(body?.events)){failures.push({source:paths[i].split("/")[0],error:"schema_invalid"});return;}
    for(const e of body.events)if(e?.id&&(!events.has(String(e.id))||e.status?.type?.state==="in"))events.set(String(e.id),{event:e,source:paths[i].split("/")[0]});
  });
  if(failures.length===paths.length)throw new Error("ALL_ESPN_SOURCES_FAILED:"+failures.map(x=>x.error).join(","));
  const normalized=[...events.values()].map(x=>parseEvent(x.event,x.source)).filter(Boolean);
  // Enrich up to 20 LIVE matches per refresh in a single parallel batch.
  // Incomplete upstream feeds remain incomplete; never invent missing statistics.
  const ESPN_DETAIL_MAX_PER_REFRESH=20;
  const ESPN_DETAIL_CONCURRENCY=20;
  const live=normalized.filter(e=>e.is_live).slice(0,ESPN_DETAIL_MAX_PER_REFRESH);
  const detail=[];
  for(let start=0;start<live.length;start+=ESPN_DETAIL_CONCURRENCY){
    const batch=live.slice(start,start+ESPN_DETAIL_CONCURRENCY);
    detail.push(...await Promise.allSettled(batch.map(e=>getEspn("all/summary?event="+e.provider_id))));
  }
  let detailSuccess=0;
  for(let i=0;i<live.length;i++){
    let extra={home:{},away:{}};
    if(detail[i].status==="fulfilled"){
      const j=detail[i].value;
      extra=fromTeams(j?.boxscore?.teams||j?.boxscore?.statistics||[],live[i].home_team_id,live[i].away_team_id);
      detailSuccess++;
    }
    const both=mergeStats(live[i]._scoreboard_stats,extra);
    live[i].live_stats=buildLiveStats(both);
    live[i].stats_sources=Object.keys(both.home).length+Object.keys(both.away).length?["espn"]:[];
  }
  for(const e of normalized){
    if(!e.is_live)e.live_stats=buildLiveStats(e._scoreboard_stats);
    delete e._scoreboard_stats;
  }
  return {events:normalized.slice(0,250),sourceEvents:events.size,feedRequests:paths.length,detailCap:ESPN_DETAIL_MAX_PER_REFRESH,detailRequested:live.length,detailSuccess,failures};
}

/**
 * Real-match-only supplementary observations.
 * SportScore proves fixture identity and live clock; MoviOdds supplies recent
 * measured corner/shot values. No provider statistics => no signal.
 * Both live feeds must agree on teams and kickoff. Explicit esports excluded.
 */
function supplementalName(value){
 return String(value||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"")
  .replace(/\(\s*w\s*\)/g," women ").replace(/\b(youth|under\s*20)\b/g," u20 ")
  .replace(/\b(rj|fc|cf|cd)\b/g," ").replace(/[^a-z0-9]+/g," ")
  .replace(/\s+/g," ").trim();
}
function supplementalRecent(value,maxAgeMs=150000){
 const when=Date.parse(value||"");
 const age=Date.now()-when;
 return Number.isFinite(when)&&age>=-30000&&age<=maxAgeMs;
}
function supplementalStatPair(stats,key,limit=400){
 const h=stats?.home?.[key],a=stats?.away?.[key];
 if(h===null||h===undefined||a===null||a===undefined)return null;
 const hv=Number(h),av=Number(a);
 return Number.isInteger(hv)&&Number.isInteger(av)&&hv>=0&&av>=0&&hv<=limit&&av<=limit?[hv,av]:null;
}
async function supplementalJson(url){
 const response=await fetch(url,{headers:{"Accept":"application/json","User-Agent":"MrXPRONOS/2.0 (+live statistics; https://mrxpronos.github.io)"},
  signal:AbortSignal.timeout(9000)});
 if(!response.ok)throw new Error("http_"+response.status);
 if(!(response.headers.get("content-type")||"").includes("json"))throw new Error("non_json");
 return response.json();
}
function supplementalFixtureIdentity(f){
 const home=String(typeof f?.home==="string"?f.home:f?.home?.name||"").trim();
 const away=String(typeof f?.away==="string"?f.away:f?.away?.name||"").trim();
 const match=String(f?.url||"").match(/\/match\/([^/?#]+)\/([^/?#]+)/);
 const slug=String(f?.slug||match?.[1]||"");
 const id=String(f?.id||f?.match_id||match?.[2]||"");
 const when=Date.parse(f?.time||f?.date||f?.start_time||"");
 return {home,away,slug,id,when};
}
async function fetchVerifiedSupplementalLive(existing){
 const report={sportscore_live:0,moviodds_live:0,matched_fixtures:0,eligible_verified:0,
  missing_stats:0,stale_stats:0,virtual_rejected:0,clock_unavailable:0,duplicate_espn:0,errors:[]};
 let fixtures,board;
 try{
  const [f,b]=await Promise.all([
   supplementalJson("https://sportscore.com/api/v1/fixtures/?sport=football&date="+new Date().toISOString().slice(0,10)+"&status=live&limit=200"),
   supplementalJson("https://moviodds.com/odds?sport=soccer&in_play=1&stats=1")
  ]);
  fixtures=Array.isArray(f?.matches)?f.matches:[];
  board=Array.isArray(b?.matches)?b.matches:[];
 }catch(e){report.errors.push("supplemental_fetch_"+String(e?.message||"error").slice(0,45));return {matches:[],report}}
 report.sportscore_live=fixtures.length;report.moviodds_live=board.length;
 const matches=[];
 for(const fixture of fixtures.slice(0,60)){
  const sf=supplementalFixtureIdentity(fixture);
  if(!sf.home||!sf.away||!sf.slug||!sf.id||!Number.isFinite(sf.when)||String(fixture.status).toLowerCase()!=="live")continue;
  const sportHome=supplementalName(sf.home),sportAway=supplementalName(sf.away);
  if(!sportHome||!sportAway)continue;
  const matched=board.filter(m=>{
   if(m?.in_play!==true)return false;
   const hm=String(m?.home??m?.home_team??m?.homeTeam?.name??"");
   const aw=String(m?.away??m?.away_team??m?.awayTeam?.name??"");
   if(/\((?!\s*w\s*\))[^)]{2,}\)/i.test(hm+" "+aw) ||
      /\b(esoccer|cyber|virtual|simulated|efootball)\b/i.test(hm+" "+aw))return false;
   const km=Date.parse(m.kickoff_utc||m.kickoff||m.starts||m.start_time||"");
   if(!Number.isFinite(km)||Math.abs(km-sf.when)>7200000)return false;
   return supplementalName(hm)===sportHome&&supplementalName(aw)===sportAway;
  });
  if(matched.length!==1)continue;
  report.matched_fixtures++;
  const m=matched[0];
  if(!supplementalRecent(m.polled_at)||!supplementalRecent(m.stats?.updated_at)){
    report.stale_stats++;continue;
  }
  const corner=supplementalStatPair(m.stats,"corners");
  const shots=supplementalStatPair(m.stats,"shots");
  const target=supplementalStatPair(m.stats,"shots_on_target");
  if(!corner&&!shots){report.missing_stats++;continue}
  if(shots&&target&&(target[0]>shots[0]||target[1]>shots[1])){report.missing_stats++;continue}
  // Never create a duplicate for the same real fixture in ESPN.
  if((existing||[]).some(x=>x.is_live &&
      supplementalName(x.home_team)===sportHome&&supplementalName(x.away_team)===sportAway&&
      Math.abs(Date.parse(x.event_date)-sf.when)<=7200000)){report.duplicate_espn++;continue}
  let detail;
  try{detail=await supplementalJson("https://sportscore.com/api/v1/match/?sport=football&slug="+encodeURIComponent(sf.slug))}
  catch(e){report.errors.push("detail_"+String(e?.message||"error").slice(0,30));continue}
  const match=detail?.match||detail?.data?.match||{};
  const liveMinute=Number(match.live_minute??match.minute??match.elapsed);
  if(!Number.isInteger(liveMinute)||liveMinute<1||liveMinute>95){
   report.clock_unavailable++;continue;
  }
  if(!["live","inprogress","in_progress"].includes(String(match.status||fixture.status).toLowerCase()))continue;
  const detailedHome=supplementalName(typeof match.home==="string"?match.home:match.home?.name);
  const detailedAway=supplementalName(typeof match.away==="string"?match.away:match.away?.name);
  if(detailedHome&&detailedAway&&(detailedHome!==sportHome||detailedAway!==sportAway))continue;
  // Score disagreement could indicate wrong identity or a lagged feed.
  const score=(v)=>v===null||v===undefined||v===""?null:Number(v);
  const fh=score(fixture.home_score),fa=score(fixture.away_score);
  const mh=score(m.home_score),ma=score(m.away_score);
  if([fh,fa,mh,ma].every(Number.isFinite)&&(fh!==mh||fa!==ma))continue;
  const home={},away={};
  for(const [key,pair] of [["corner_kicks",corner],["total_shots",shots],["shots_on_target",target]]){
    if(pair){home[key]=pair[0];away[key]=pair[1]}
  }
  const pos=supplementalStatPair(m.stats,"possession",100);
  if(pos){home.ball_possession=pos[0];away.ball_possession=pos[1]}
  const league=typeof fixture.competition==="string"?fixture.competition:
    String(fixture.competition?.name||"Football");
  matches.push({
    id:"sportscore:"+sf.id,provider_id:String(m.id),source_name:"moviodds",
    home_team:sf.home,away_team:sf.away,home_score:fh??mh??0,away_score:fa??ma??0,
    current_minute:liveMinute,event_date:new Date(sf.when).toISOString(),
    league_name:league.slice(0,200),status:"inprogress",period:"",
    home_logo:String(fixture.home_logo||""),away_logo:String(fixture.away_logo||""),
    is_live:true,is_finished:false,stats_sources:["sportscore_fixture","moviodds_verified"],
    live_stats:buildLiveStats({home,away})
  });
  report.eligible_verified++;
  if(matches.length>=12)break;
 }
 return {matches,report};
}

function diagnostic(events) {
  const live=events.filter(e=>e.is_live);
  const scheduled=events.filter(e=>!e.is_live);
  const observed=live.filter(e=>Object.keys(e.live_stats.home||{}).length+Object.keys(e.live_stats.away||{}).length>0);
  const paired=(key)=>live.filter(e=>Number.isFinite(e.live_stats?.home?.[key])&&Number.isFinite(e.live_stats?.away?.[key]));
  return {live_matches:live.length,scheduled_matches:scheduled.length,
    live_with_corner_pairs:paired("corner_kicks").length,
    live_with_shot_pairs:paired("total_shots").length,
    live_with_foul_pairs:paired("fouls").length,
    live_with_observed_statistics:observed.length,statistics_fields:observed.reduce((acc,e)=>acc+Object.keys(e.live_stats.home||{}).length+Object.keys(e.live_stats.away||{}).length,0),
    generated_signals:0,telegram_sent:0};
}
async function persistRefresh(events,fetchDetails) {
  const owner=crypto.randomUUID();
  const lock=await sql.unsafe(
    "INSERT INTO public.worker_locks(lock_name,locked_at,expires_at,owner) VALUES ('neon_live_refresh',now(),now()+interval '120 seconds',$1) ON CONFLICT(lock_name) DO UPDATE SET locked_at=now(),expires_at=now()+interval '120 seconds',owner=EXCLUDED.owner WHERE public.worker_locks.expires_at<now() RETURNING lock_name",
    [owner]
  );
  if(!lock.length)return {already_running:true,success:false,telegram_sent:0};
  try{
    // One atomic transaction: failed upstream batches never mark refresh healthy.
    return await sql.begin(async tx=>{
      const encoded=JSON.stringify(events);
      const liveCount=events.filter(e=>e.is_live).length;
      const scheduledCount=events.filter(e=>!e.is_live).length;
      if(events.length){
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements(CASE WHEN jsonb_typeof($1::jsonb)='string' THEN ($1::jsonb #>> '{}')::jsonb ELSE $1::jsonb END))"+
          " INSERT INTO public.matches_live(id,home_team,away_team,home_score,away_score,current_minute,league_name,status,raw_data,updated_at)"+
          " SELECT e->>'id',e->>'home_team',e->>'away_team',(e->>'home_score')::int,(e->>'away_score')::int,(e->>'current_minute')::int,e->>'league_name',e->>'status',e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(id) DO UPDATE SET home_team=EXCLUDED.home_team,away_team=EXCLUDED.away_team,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,current_minute=EXCLUDED.current_minute,league_name=EXCLUDED.league_name,status=EXCLUDED.status,raw_data=EXCLUDED.raw_data,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements(CASE WHEN jsonb_typeof($1::jsonb)='string' THEN ($1::jsonb #>> '{}')::jsonb ELSE $1::jsonb END))"+
          " INSERT INTO public.live_scheduled_fixtures(fixture_id,event_date,home_team,away_team,source_names,fixture,updated_at)"+
          " SELECT e->>'id',(e->>'event_date')::timestamptz,e->>'home_team',e->>'away_team',ARRAY['espn']::text[],e,now() FROM src WHERE e->>'is_live'='false'"+
          " ON CONFLICT(fixture_id) DO UPDATE SET event_date=EXCLUDED.event_date,home_team=EXCLUDED.home_team,away_team=EXCLUDED.away_team,source_names=EXCLUDED.source_names,fixture=EXCLUDED.fixture,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements(CASE WHEN jsonb_typeof($1::jsonb)='string' THEN ($1::jsonb #>> '{}')::jsonb ELSE $1::jsonb END))"+
          " INSERT INTO public.live_stats_sources(canonical_match_id,source_name,source_match_id,home_team,away_team,league_name,event_date,minute,home_score,away_score,is_live,is_finished,stats_json,raw_json,updated_at)"+
          " SELECT e->>'id',COALESCE(e->>'source_name','espn'),e->>'provider_id',e->>'home_team',e->>'away_team',e->>'league_name',(e->>'event_date')::timestamptz,(e->>'current_minute')::int,(e->>'home_score')::int,(e->>'away_score')::int,true,false,e->'live_stats',e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(source_name,source_match_id) DO UPDATE SET minute=EXCLUDED.minute,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,stats_json=EXCLUDED.stats_json,raw_json=EXCLUDED.raw_json,updated_at=EXCLUDED.updated_at",
          [encoded]);
        await tx.unsafe(
          "WITH src AS (SELECT value AS e FROM jsonb_array_elements(CASE WHEN jsonb_typeof($1::jsonb)='string' THEN ($1::jsonb #>> '{}')::jsonb ELSE $1::jsonb END))"+
          " INSERT INTO public.live_stats_merged(canonical_match_id,primary_match_id,home_team,away_team,league_name,event_date,minute,home_score,away_score,is_live,is_finished,merged_stats,sources_used,confidence_score,merged_match_json,updated_at)"+
          " SELECT e->>'id',e->>'id',e->>'home_team',e->>'away_team',e->>'league_name',(e->>'event_date')::timestamptz,(e->>'current_minute')::int,(e->>'home_score')::int,(e->>'away_score')::int,true,false,e->'live_stats',COALESCE(e->'stats_sources','[\"espn\"]'::jsonb),50,e,now() FROM src WHERE e->>'is_live'='true'"+
          " ON CONFLICT(canonical_match_id) DO UPDATE SET minute=EXCLUDED.minute,home_score=EXCLUDED.home_score,away_score=EXCLUDED.away_score,merged_stats=EXCLUDED.merged_stats,merged_match_json=EXCLUDED.merged_match_json,updated_at=EXCLUDED.updated_at",
          [encoded]);
      }
      const stats=diagnostic(events);
      const report={...stats,engine:"neon-espn-safe-v1",source_events:fetchDetails.sourceEvents,
        feed_requests:fetchDetails.feedRequests,detail_requests:fetchDetails.detailRequested,detail_cap:fetchDetails.detailCap,
        detail_parallel_limit:20,detail_target_when_available:20,
        detail_success:fetchDetails.detailSuccess,failures:fetchDetails.failures,supplemental:fetchDetails.supplemental,
        no_telegram:true,no_signal_generation:true};
      await tx.unsafe(
        "INSERT INTO public.cron_runs(name,last_run_at,last_ok,meta) VALUES ('live_refresh',now(),true,$1::text::jsonb) ON CONFLICT(name) DO UPDATE SET last_run_at=EXCLUDED.last_run_at,last_ok=EXCLUDED.last_ok,meta=EXCLUDED.meta",
        [JSON.stringify(report)]
      );
      return {success:true,...report};
    });
  }finally{
    await sql.unsafe("DELETE FROM public.worker_locks WHERE lock_name='neon_live_refresh' AND owner=$1",[owner]).catch(()=>{});
  }
}
// Instant Telegram dispatch after the live_predictions transaction has committed.
// The Cloudflare endpoint is HMAC-verified and holds Telegram tokens as secrets.
const INSTANT_TELEGRAM_URL="https://mrxpronos-live-telegram-instant.cinecanaux-xpronos.workers.dev/deliver";
async function dispatchInstantTelegram(){
  const secret=process.env.NEON_DELIVERY_HMAC_KEY||"";
  const summary={telegram_delivery:"disabled",telegram_delivery_attempted:0,telegram_delivery_confirmed:0,telegram_delivery_pending:0};
  if(!secret)return summary;
  summary.telegram_delivery="ready";
  let candidates;
  try{
    candidates=await sql.unsafe(
      "SELECT p.id::text AS id,p.match_id,p.created_at,p.model_version,p.pricing_mode,"+
      "p.prediction_type AS type,p.signal_tier,p.home_team,p.away_team,p.probability,"+
      "p.threshold,p.signal_value,p.reliability_score AS reliability,p.data_quality_score,p.minute,"+
      "p.home_score,p.away_score,p.league_name,p.model_fair_odds,"+
      "m.raw_data->>'home_logo' AS home_logo,m.raw_data->>'away_logo' AS away_logo "+
      "FROM public.live_predictions p JOIN public.matches_live m ON p.match_id=m.id "+
      "WHERE p.model_version=$1 AND p.created_at>=now()-interval '14 minutes' "+
      "AND p.created_at<=now()+interval '30 seconds' AND COALESCE(p.telegram_sent,false)=false "+
      "AND COALESCE(p.validated,false)=false AND m.updated_at>=now()-interval '3 minutes' "+
      "AND m.raw_data->>'is_live'='true' ORDER BY p.created_at ASC LIMIT 12",
      [NEON_SIGNAL_MODEL_VERSION]
    );
  }catch(e){
    console.error("NEON_TELEGRAM_OUTBOX_QUERY_FAILED",e?.code||e?.name);
    return {...summary,telegram_delivery:"db_error"};
  }
  if(!candidates.length){
    // Signed empty request confirms that the Neon function reaches Cloudflare.
    // This never calls Telegram, and reveals network/WAF issues in cron health.
    try{
      const payload=JSON.stringify({signals:[]}),ts=String(Date.now());
      const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(secret),
        {name:"HMAC",hash:"SHA-256"},false,["sign"]);
      const signature=Buffer.from(await crypto.subtle.sign("HMAC",key,new TextEncoder().encode(ts+"."+payload))).toString("hex");
      const resp=await fetch(INSTANT_TELEGRAM_URL,{method:"POST",
        headers:{"content-type":"application/json","x-mrx-timestamp":ts,"x-mrx-signature":signature},
        body:payload,signal:AbortSignal.timeout(9000)});
      const result=await resp.json().catch(()=>({}));
      summary.telegram_delivery=resp.ok&&result.ok===true?"idle_verified":"gateway_http_"+resp.status;
    }catch(e){
      summary.telegram_delivery="gateway_network_"+String(e?.name||"error").slice(0,20);
    }
    return summary;
  }
  const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(secret),
    {name:"HMAC",hash:"SHA-256"},false,["sign"]);
  async function one(row){
    const payload=JSON.stringify({signals:[{
      id:String(row.id),match_id:row.match_id,created_at:row.created_at,model_version:row.model_version,
      pricing_mode:row.pricing_mode,type:row.type,signal_tier:row.signal_tier,
      home_team:row.home_team,away_team:row.away_team,
      home_logo:row.home_logo||null,away_logo:row.away_logo||null,
      home_score:row.home_score,away_score:row.away_score,league_name:row.league_name||"Football",
      model_fair_odds:Number(row.model_fair_odds),
      probability:Number(row.probability),threshold:Number(row.threshold),
      signal_value:Number(row.signal_value),reliability:Number(row.reliability),
      data_quality_score:Number(row.data_quality_score),minute:Number(row.minute)
    }]});
    const ts=String(Date.now());
    const signature=Buffer.from(await crypto.subtle.sign("HMAC",key,new TextEncoder().encode(ts+"."+payload))).toString("hex");
    let status="worker_unavailable",deliveryConfirmed=0,pending=1;
    try{
      const response=await fetch(INSTANT_TELEGRAM_URL,{method:"POST",
        headers:{"content-type":"application/json","x-mrx-timestamp":ts,"x-mrx-signature":signature},
        body:payload,signal:AbortSignal.timeout(18000)});
      const result=await response.json().catch(()=>({}));
      if(response.ok&&result.ok===true){
        const d=result.results?.[0];
        if(d?.prediction_id===String(row.id)&&d.all_sent===true){
          status="sent";deliveryConfirmed=d.deliveries?.length||0;pending=0;
        }else status="unresolved";
      }else status="worker_http_"+response.status;
    }catch(e){status="transport_"+String(e?.name||"error").slice(0,24);}
    try{
      await sql.unsafe(
        "UPDATE public.live_predictions SET telegram_sent=$1,telegram_sent_at=CASE WHEN $1 THEN now() ELSE telegram_sent_at END,"+
        "telegram_attempts=COALESCE(telegram_attempts,0)+1,telegram_last_attempt_at=now(),"+
        "telegram_last_error=CASE WHEN $1 THEN NULL ELSE $2 END WHERE id=$3::uuid",
        [status==="sent",status==="sent"?null:status,String(row.id)]
      );
    }catch(e){console.error("NEON_TELEGRAM_DELIVERY_UPDATE_FAILED",e?.code||e?.name);}
    return {status,confirmed:deliveryConfirmed,pending};
  }
  // 4 simultaneous HTTP calls; avoid slowing down the one-minute refresh.
  for(let i=0;i<candidates.length;i+=4){
    const settled=await Promise.allSettled(candidates.slice(i,i+4).map(one));
    for(const item of settled){
      summary.telegram_delivery_attempted++;
      if(item.status==="fulfilled"){
        summary.telegram_delivery_confirmed+=item.value.confirmed;
        summary.telegram_delivery_pending+=item.value.pending;
      }else summary.telegram_delivery_pending++;
    }
  }
  summary.telegram_delivery=summary.telegram_delivery_pending?"partial":"ok";
  return summary;
}

const oldNeonLiveFetch=index_default.fetch.bind(index_default);
index_default.fetch=async function(req){
  const path=new URL(req.url).pathname.replace(/\/$/,"");
  if(path!=="/refresh"&&path!=="/functions/v1/live/refresh")return oldNeonLiveFetch(req);
  if(req.method==="OPTIONS")return new Response(null,{status:204,headers:{...headers(req),"access-control-allow-methods":"POST,OPTIONS","access-control-allow-headers":"authorization,content-type"}});
  if(req.method!=="POST")return json(req,{error:"method_not_allowed"},405);
  const body=await req.json().catch(()=>({}));
  // Neon strips client-originated X-Neon-* headers at its edge.
  // Only a native schedule trigger can supply this trusted header.
  const invocation=req.headers.get("x-neon-trigger-invocation-id")||"";
  const scheduledAt=Date.parse(body?.data?.scheduled_at||"");
  const nativeSchedule=!!(invocation && body?.invocation_id===invocation &&
      body?.trigger?.type==="schedule" && body?.trigger?.name==="mrxpronos-live-refresh-v1" &&
      Number.isFinite(scheduledAt) && Math.abs(Date.now()-scheduledAt)<=20*60*1000);
  if(!nativeSchedule && !(await verifyGithubOidc(req)))return json(req,{error:"unauthorized"},401);
  const mode=nativeSchedule?"apply":body?.mode;
  if(!["preview","apply"].includes(mode))return json(req,{error:"invalid_mode"},400);
  try {
    const pulled=await fetchFromESPN();
    const supplementary=await fetchVerifiedSupplementalLive(pulled.events);
    pulled.events.push(...supplementary.matches);
    pulled.supplemental=supplementary.report;
    const summary=diagnostic(pulled.events);
    if(mode==="preview")return json(req,{success:true,mode:"preview",...summary,source_events:pulled.sourceEvents,feed_requests:pulled.feedRequests,detail_success:pulled.detailSuccess,detail_cap:pulled.detailCap,failures:pulled.failures,supplemental:pulled.supplemental,no_database_writes:true});
    const report=await persistRefresh(pulled.events,pulled);
    if(report.already_running)return json(req,{mode:"apply",...report},409);
    let signalReport={generated_signals:0,validation_successes:0,notifications_created:0,signal_backend:"ready"};
    try {
      signalReport=await sql.begin(async tx=>{
        const sr=await storeModelSignals(tx,pulled.events);
        const merged={...sr,no_signal_generation:false};
        await tx.unsafe("UPDATE public.cron_runs SET meta=COALESCE(meta,'{}'::jsonb) || $1::text::jsonb WHERE name='live_refresh'",
          [JSON.stringify(merged)]);
        return {...sr,signal_backend:"active"};
      });
    } catch (signalError) {
      console.error("NEON_SIGNAL_PERSIST_FAILED",signalError?.code||signalError?.name,
        String(signalError?.message||"").slice(0,190));
      signalReport={generated_signals:0,validation_successes:0,notifications_created:0,
        signal_backend:"error",signal_error:String(signalError?.code||signalError?.name||"unknown").slice(0,40)};
    }
    let delivery={telegram_delivery:"not_attempted",telegram_delivery_attempted:0,telegram_delivery_confirmed:0,telegram_delivery_pending:0};
    if(signalReport.signal_backend==="active"){
      try{delivery=await dispatchInstantTelegram();}
      catch(e){console.error("NEON_INSTANT_TELEGRAM_FAILED",e?.code||e?.name);delivery.telegram_delivery="failed";}
    }
    try {
      await sql.unsafe("UPDATE public.cron_runs SET meta=COALESCE(meta,'{}'::jsonb) || $1::text::jsonb WHERE name='live_refresh'",
        [JSON.stringify(delivery)]);
    }catch(e){console.error("NEON_TELEGRAM_HEALTH_SAVE_FAILED",e?.code||e?.name);}
    return json(req,{mode:"apply",...report,...signalReport,...delivery,
      no_signal_generation:signalReport.signal_backend!=="active"},200);
  }catch(e){
    console.error("NEON_REFRESH_FAILED",e?.code||e?.name,String(e?.message||"").slice(0,250));
    return json(req,{success:false,error:"refresh_failed",reason:String(e?.code||e?.message||"unknown").slice(0,140),telegram_sent:0},503);
  }
};

// Reprise conservatrice du modele live-value-v2.3-playability-envelope de
// supabase/functions/live/index.ts (2026-10-22). Sans source bookmaker ni Telegram.
// No empirical accuracy claims. Model-only implied odds are NOT bookmaker odds.
const NEON_SIGNAL_MODEL_VERSION = "neon-live-value-v2.3-playability-espn";
const MARKETS = {
  corners:{ stat:"corner_kicks", db:"total_corners", unit:"corners",
    lines:[7.5,8.5,9.5,10.5,11.5,12.5,13.5],
    baseline:[7.5,8.5,9.5,10.5,11.5], first:18,last:82,min:3,
    probability:.58,reliability:52},
  shots:{ stat:"total_shots",db:"total_shots",unit:"tirs",
    lines:[15.5,17.5,19.5,21.5,23.5,25.5,27.5,29.5,31.5,33.5],
    baseline:[17.5,19.5,21.5,23.5,25.5,27.5,29.5],
    first:15,last:83,min:6,probability:.60,reliability:55},
  fouls:{stat:"fouls",db:"total_fouls",unit:"fautes",
    lines:[17.5,19.5,21.5,23.5,24.5,25.5,27.5,29.5,31.5],
    baseline:[19.5,21.5,23.5,24.5,25.5,27.5],
    first:18,last:84,min:6,probability:.57,reliability:54}
};
const num=(v)=>v===null||v===undefined||v===""?null:(Number.isFinite(Number(v))?Number(v):null);
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const round=(n,d=2)=>Number(n.toFixed(d));
function pair(stats,key){
  const h=num(stats?.home?.[key]),a=num(stats?.away?.[key]);
  return h!==null&&a!==null&&h>=0&&a>=0&&h<10000&&a<10000 ? h+a : null;
}
function momentum(stats){
  const m=(side)=>side?2*(num(side.total_shots)||0)+3*(num(side.shots_on_target)||0)+1.5*(num(side.corner_kicks)||0)+.15*(num(side.ball_possession)||0):0;
  return {total:Math.round(m(stats?.home)+m(stats?.away))};
}
function matchFlow(stats,minute,mom){
  const shots=pair(stats,"total_shots")||0,corners=pair(stats,"corner_kicks")||0;
  const shotOn=pair(stats,"shots_on_target")||0;
  const ph=num(stats?.home?.ball_possession)||0,pa=num(stats?.away?.ball_possession)||0;
  const shotRate=shots/Math.max(1,minute),cornerRate=corners/Math.max(1,minute);
  const pressure=shotOn*2+corners*1.4+Math.abs(ph-pa)*.08+(mom?.total||0)*.12;
  let flow="neutral";
  if(pressure>=18||shotRate>=.22||cornerRate>=.09)flow="offensive";
  if(minute>=65&&pressure<12&&shotRate<.18&&cornerRate<.07)flow="defensive";
  return flow;
}
function projection(current,minute,type,flow){
  const elapsed=Math.max(1,minute),left=Math.max(0,90-elapsed);
  let multiplier=flow==="offensive"?.82:flow==="defensive"?.52:.70;
  if(minute>=70)multiplier-=.08;
  if(minute>=78)multiplier-=.10;
  multiplier=Math.max(.35,multiplier);
  const extra=type==="corners"?4:8;
  return round(Math.min(current+(current/elapsed)*left*multiplier,current+extra),1);
}
function poissonTail(lambda,atLeast){
  if(atLeast<=0)return 1;
  if(!(lambda>0))return 0;
  let term=Math.exp(-lambda),sum=term;
  for(let i=1;i<atLeast;i++){term*=lambda/i;sum+=term;}
  return clamp(1-sum,.005,.995);
}
function probability(current,threshold,projected,heuristic,reliability){
  const additional=Math.max(0,Math.floor(threshold)+1-current);
  const ct=poissonTail(Math.max(.05,projected-current),additional);
  const blended=ct*.72+clamp(heuristic,.20,.95)*.18+.05;
  const val=.50+(blended-.50)*(.72+clamp(reliability/100,0,1)*.28);
  return round(clamp(val,.18,.94),4);
}
function tier(fairOdds){
  if(fairOdds>=1.45&&fairOdds<=1.75)return "quality";
  if(fairOdds>1.75&&fairOdds<=2.30)return "value";
  if(fairOdds>2.30&&fairOdds<=3.20)return "high_value";
  return null;
}
function tierQuality(t,p,rel,dq){
  if(t==="quality")return p>=.56&&rel>=68&&dq>=67;
  if(t==="value")return p>=.43&&rel>=72&&dq>=67;
  if(t==="high_value")return p>=.31&&rel>=78&&dq>=100;
  return false;
}
function uplift(type,minute){
  if(type==="corners")return minute<45?3:minute<60?2:1;
  if(type==="shots")return minute<45?6:minute<60?4:minute<75?2:1;
  return minute<45?4:minute<60?3:minute<75?2:1;
}
function historicalUplift(type,minute){
  if(type==="shots")return minute<30?6:minute<45?5:minute<60?2:minute<75?1:0;
  if(type==="corners")return minute>=30&&minute<45?1:0;
  return null;
}
function dataQuality(stats,type){
  const shots=pair(stats,"total_shots")!==null, corners=pair(stats,"corner_kicks")!==null;
  const on=pair(stats,"shots_on_target")!==null,fouls=pair(stats,"fouls")!==null;
  if(type==="corners")return corners?(shots&&on?100:82):0;
  if(type==="shots")return shots?(on?100:82):0;
  return fouls?(corners||shots?100:82):0;
}
function gates(type,stats,minute,current,flow){
  let p=MARKETS[type].probability,r=MARKETS[type].reliability;
  const shots=pair(stats,"total_shots")||0,on=pair(stats,"shots_on_target")||0;
  if(type==="shots"){
    if(current>=8){p+=.06;r+=6}
    if(on>=3){p+=.06;r+=5}
    if(flow==="offensive"){p+=.08;r+=7}
    if(flow==="defensive"){p-=.10;r-=8}
    if(minute>=20&&minute<=72){p+=.05;r+=5}
  }else if(type==="corners"){
    if(current>=4){p+=.06;r+=6}
    if(shots>=10){p+=.06;r+=5}
    if(on>=4){p+=.04;r+=4}
    if(flow==="offensive"){p+=.07;r+=7}
    if(flow==="defensive"){p-=.08;r-=8}
    if(minute>=25&&minute<=70){p+=.05;r+=6}
  }else{
    if(current>=8){p+=.05;r+=6}
    if(minute>=25&&minute<=75){p+=.05;r+=5}
    if(flow==="defensive"){p+=.03;r+=3}
    if(flow==="offensive"){p-=.03;r-=2}
  }
  const limit=type==="shots"?.91:type==="corners"?.90:.88;
  const maxR=type==="shots"?93:type==="corners"?92:90;
  return {heuristic:clamp(p,.5,limit),reliability:clamp(r,40,maxR)};
}
function valueScore(signal){
  return clamp(Math.round(signal.reliability*.35+signal.data_quality_score*.30+
    clamp((signal.model_fair_odds-1.3)*20,0,25)),0,99);
}
function evaluateNeonLiveMatch(match,{maximumAgeSeconds=180}={}){
  const result={signals:[],rejects:{},evaluated_markets:0};
  if(!match?.is_live||match?.is_finished){result.rejects.match_not_live=1;return result}
  const minute=num(match.current_minute);
  const ageSeconds=num(match.freshness_seconds);
  if(ageSeconds===null||ageSeconds<0||ageSeconds>maximumAgeSeconds){
    result.rejects.stale=1;return result;
  }
  if(minute===null||minute<1||minute>95){result.rejects.minute_invalid=1;return result}
  const stats=match.live_stats||{},mom=momentum(stats),flow=matchFlow(stats,minute,mom);
  for(const [type,market] of Object.entries(MARKETS)){
    const reject=(why)=>{result.rejects[type+"_"+why]=(result.rejects[type+"_"+why]||0)+1};
    const current=pair(stats,market.stat);
    if(current===null){reject("missing_pair");continue}
    if(!Number.isInteger(current)){reject("not_integer");continue}
    if(minute<market.first||minute>market.last){reject("minute_gate");continue}
    if(current<market.min){reject("minimum_gate");continue}
    result.evaluated_markets++;
    const f=type==="fouls"&&flow==="offensive"?"neutral":flow;
    const projected=projection(current,minute,type,f);
    const {heuristic,reliability}=gates(type,stats,minute,current,flow);
    if(reliability<(type==="shots"?64:type==="corners"?63:62) ||
       type==="corners"&&minute>=45&&minute<60&&reliability<78){reject("weak_reliability");continue}
    const quality=dataQuality(stats,type);
    const baseline=market.baseline.find(line=>current<line&&line-current>=2&&projected>=line+.5)??null;
    if((type==="corners"||type==="shots")&&baseline===null){reject("baseline_unavailable");continue}
    const modelBuffer=type==="corners"?1.5:type==="shots"?6:3;
    const maxUplift=uplift(type,minute);
    const minProb=type==="corners"?(minute>=75?.55:.52):minute>=75?.54:.50;
    const minHeadroom=type==="corners"?(minute>=75?.5:1):minute>=60?1.5:2;
    const candidates=[];
    for(const threshold of market.lines){
      if(!(current<threshold&&threshold-current>=2&&threshold<=projected+modelBuffer))continue;
      const p=probability(current,threshold,projected,heuristic,reliability);
      const fair=round(1/p,2),t=tier(fair);
      if((type==="corners"||type==="fouls")&&t==="high_value")continue;
      if(baseline!==null&&(threshold<baseline||threshold>baseline+maxUplift))continue;
      if(p<minProb||projected-threshold<minHeadroom)continue;
      if(!tierQuality(t,p,reliability,quality))continue;
      candidates.push({threshold,probability:p,model_fair_odds:fair,signal_tier:t});
    }
    if(!candidates.length){reject("model_quality");continue}
    // Historical market-facing candidate is the highest eligible line.
    const chosen=candidates[candidates.length-1];
    const signal={
      type:market.db,threshold:chosen.threshold,probability:chosen.probability,
      model_fair_odds:chosen.model_fair_odds,signal_tier:chosen.signal_tier,
      signal_value:current,current_value:current,projected_value:projected,
      reliability, data_quality_score:quality,source_count:1,source_confidence:65,
      pricing_mode:"model_only",bookmaker_odds:null,live_odds:null,odds_source:null,
      line_candidate_count:candidates.length,line_candidate_rank:candidates.length,
      baseline_threshold:baseline,historical_uplift_cap:historicalUplift(type,minute),
      selected_uplift:baseline===null?null:round(chosen.threshold-baseline),
      model_version:NEON_SIGNAL_MODEL_VERSION,
      confidence:reliability>=80?"high":"medium",
      freshness_seconds:ageSeconds,
      message:current+" "+market.unit+" actuellement",
      reasons:["Projection finale "+projected,"Ligne modèle "+chosen.threshold],
      title:"Over "+chosen.threshold+" "+market.unit,
      headroom:round(projected-chosen.threshold)
    };
    signal.value_score=valueScore(signal);
    result.signals.push(signal);
  }
  result.signals.sort((a,b)=>b.value_score-a.value_score);
  return result;
}

// Neon native LIVE signals; no Telegram calls or bookmaker claims.
async function storeModelSignals(tx,events){
  const result={generated_signals:0,already_open:0,validation_successes:0,notifications_created:0,markets_evaluated:0,rejection_reasons:{},telegram_sent:0};
  for(const match of (events||[]).filter(e=>e.is_live).slice(0,80)){
    const evaluated=evaluateNeonLiveMatch({...match,freshness_seconds:0});
    result.markets_evaluated+=evaluated.evaluated_markets;
    for(const [key,value] of Object.entries(evaluated.rejects))
      result.rejection_reasons[key]=(result.rejection_reasons[key]||0)+value;
    for(const [predictionType,statsKey] of [
      ["total_shots","total_shots"],["total_corners","corner_kicks"],["total_fouls","fouls"]
    ]){
      const current=statPairForValidation(match.live_stats,statsKey);
      if(current===null)continue;
      // Process ONLY predictions generated by the Neon model. Migrated history is untouched.
      const updated=await tx.unsafe(
        "UPDATE public.live_predictions SET "+
        "current_value=GREATEST(COALESCE(current_value,0),$1::numeric),"+
        "validated=(GREATEST(COALESCE(current_value,0),$1::numeric)>threshold),"+
        "outcome=CASE WHEN GREATEST(COALESCE(current_value,0),$1::numeric)>threshold THEN 'success' ELSE outcome END,"+
        "validation_type=CASE WHEN GREATEST(COALESCE(current_value,0),$1::numeric)>threshold THEN 'instant' ELSE validation_type END,"+
        "validated_at=CASE WHEN GREATEST(COALESCE(current_value,0),$1::numeric)>threshold THEN now() ELSE validated_at END,"+
        "updated_at=now() "+
        "WHERE match_id=$2 AND prediction_type=$3 AND model_version=$4 "+
        "AND validated=false AND created_at>=now()-interval '130 minutes' "+
        "RETURNING id,threshold,validated",
        [current,match.id,predictionType,NEON_SIGNAL_MODEL_VERSION]
      );
      for(const row of updated){
        if(!row.validated)continue;
        result.validation_successes++;
        const msg=match.home_team+" vs "+match.away_team+"\n"+
          "Marché: "+predictionType+"\nSeuil: "+row.threshold+
          "\nRésultat observé: "+current+"\nMinute: "+match.current_minute+"'";
        await tx.unsafe(
          "INSERT INTO public.notifications(user_id,type,title,message,priority,read,related_prediction_id,created_at) "+
          "VALUES ('all','prediction_reached','Pronostic atteint en LIVE',$1,'normal',false,$2,now())",
          [msg,String(row.id)]
        );
        result.notifications_created++;
      }
    }
    for(const pred of evaluated.signals){
      // Keep a 90-minute per-match/per-market cooldown.
      const rows=await tx.unsafe(
        "INSERT INTO public.live_predictions("+
        "match_id,match_name,home_team,away_team,home_score,away_score,minute,league_name,"+
        "prediction_type,probability,message,threshold,current_value,projected_value,confidence,"+
        "signal_value,reliability_score,model_fair_odds,value_score,data_quality_score,"+
        "freshness_seconds,source_count,source_confidence,signal_tier,pricing_mode,"+
        "line_candidate_count,line_candidate_rank,baseline_threshold,historical_uplift_cap,"+
        "selected_uplift,model_version,signal_home_score,signal_away_score,signal_minute,"+
        "created_at,updated_at,telegram_sent,telegram_attempts,telegram_pending_chat_ids,"+
        "live_odds,bookmaker_odds,implied_probability,edge,expected_value) "+
        "SELECT $1,$2,$3,$4,$5::int,$6::int,$7::int,$8,"+
        "$9,$10::numeric,$11,$12::numeric,$13::numeric,$14::numeric,$15,"+
        "$16::numeric,$17::numeric,$18::numeric,$19::numeric,$20::numeric,"+
        "$21::int,$22::int,$23::numeric,$24,$25,"+
        "$26::int,$27::int,$28::numeric,$29::numeric,"+
        "$30::numeric,$31,$32::int,$33::int,$34::numeric,"+
        "now(),now(),false,0,'{}'::text[],NULL,NULL,NULL,NULL,NULL "+
        "WHERE NOT EXISTS(SELECT 1 FROM public.live_predictions p "+
        " WHERE p.match_id=$1 AND p.prediction_type=$9 AND p.model_version=$31 "+
        " AND p.created_at>now()-interval '90 minutes') "+
        "ON CONFLICT DO NOTHING RETURNING id",
        [
          match.id,match.home_team+" vs "+match.away_team,
          match.home_team,match.away_team,
          match.home_score,match.away_score,match.current_minute,
          match.league_name||"Football",pred.type,pred.probability,pred.message,
          pred.threshold,pred.current_value,pred.projected_value,pred.confidence,
          pred.signal_value,pred.reliability,pred.model_fair_odds,pred.value_score,
          pred.data_quality_score,pred.freshness_seconds,pred.source_count,
          pred.source_confidence,pred.signal_tier,pred.pricing_mode,
          pred.line_candidate_count,pred.line_candidate_rank,pred.baseline_threshold,
          pred.historical_uplift_cap,pred.selected_uplift,pred.model_version,
          match.home_score,match.away_score,match.current_minute
        ]
      );
      if(!rows?.length){result.already_open++;continue}
      result.generated_signals++;
      const id=String(rows[0].id);
      const msg=match.home_team+" vs "+match.away_team+
        "\nPronostic: "+pred.title+"\nMinute du signal: "+match.current_minute+"'"+
        "\nAu signal: "+pred.signal_value+
        "\nCote bookmaker non disponible : estimation du modèle uniquement. 18+.";
      await tx.unsafe(
        "INSERT INTO public.notifications(user_id,type,title,message,priority,read,related_prediction_id,created_at) "+
        "VALUES ('all','live_prediction','Nouvelle opportunité LIVE',$1,'normal',false,$2,now())",
        [msg,id]
      );
      result.notifications_created++;
    }
  }
  return result;
}
function statPairForValidation(stats,key){
  const h=stats?.home?.[key],a=stats?.away?.[key];
  if(h===null||h===undefined||a===null||a===undefined)return null;
  const x=Number(h),y=Number(a);
  return Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&y>=0?x+y:null;
}
const neonLiveHandlerBeforeNotifications=index_default.fetch.bind(index_default);
index_default.fetch=async function(req){
  const url=new URL(req.url),path=url.pathname.replace(/\/$/,"");
  if(path==="/notifications"||path==="/functions/v1/live/notifications"){
    if(req.method==="OPTIONS")return new Response(null,{status:204,headers:{
      ...headers(req),"access-control-allow-methods":"GET,OPTIONS",
      "access-control-allow-headers":"content-type"}});
    if(req.method!=="GET")return json(req,{error:"method_not_allowed"},405);
    try{
      // Broadcast notifications only. user_id query parameter is ignored.
      const items=await sql.unsafe(
        "SELECT id,type,title,message,priority,read,related_prediction_id,created_at "+
        "FROM public.notifications WHERE user_id='all' "+
        "AND created_at>=now()-interval '7 days' ORDER BY created_at DESC LIMIT 75",[]);
      return json(req,{notifications:items});
    }catch(e){
      console.error("NEON_NOTIFICATIONS_READ_FAILED",e?.code||e?.name);
      return json(req,{error:"database_unavailable"},503);
    }
  }
  if(path==="/notifications/mark-read"||path==="/functions/v1/live/notifications/mark-read"){
    return json(req,{error:"read_status_is_local_to_browser"},405);
  }
  return neonLiveHandlerBeforeNotifications(req);
};

}
