var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __require = /* @__PURE__ */ ((x) => typeof require !== "undefined" ? require : typeof Proxy !== "undefined" ? new Proxy(x, {
  get: (a, b2) => (typeof require !== "undefined" ? require : a)[b2]
}) : x)(function(x) {
  if (typeof require !== "undefined") return require.apply(this, arguments);
  throw Error('Dynamic require of "' + x + '" is not supported');
});
var __esm = (fn, res) => function __init() {
  return fn && (res = (0, fn[__getOwnPropNames(fn)[0]])(fn = 0)), res;
};
var __commonJS = (cb, mod) => function __require2() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// node_modules/@resvg/resvg-wasm/index.mjs
var resvg_wasm_exports = {};
__export(resvg_wasm_exports, {
  Resvg: () => Resvg2,
  initWasm: () => initWasm
});
function addHeapObject(obj) {
  if (heap_next === heap.length)
    heap.push(heap.length + 1);
  const idx = heap_next;
  heap_next = heap[idx];
  heap[idx] = obj;
  return idx;
}
function getObject(idx) {
  return heap[idx];
}
function dropObject(idx) {
  if (idx < 132)
    return;
  heap[idx] = heap_next;
  heap_next = idx;
}
function takeObject(idx) {
  const ret = getObject(idx);
  dropObject(idx);
  return ret;
}
function getUint8Memory0() {
  if (cachedUint8Memory0 === null || cachedUint8Memory0.byteLength === 0) {
    cachedUint8Memory0 = new Uint8Array(wasm.memory.buffer);
  }
  return cachedUint8Memory0;
}
function passStringToWasm0(arg, malloc, realloc) {
  if (realloc === void 0) {
    const buf = cachedTextEncoder.encode(arg);
    const ptr2 = malloc(buf.length, 1) >>> 0;
    getUint8Memory0().subarray(ptr2, ptr2 + buf.length).set(buf);
    WASM_VECTOR_LEN = buf.length;
    return ptr2;
  }
  let len = arg.length;
  let ptr = malloc(len, 1) >>> 0;
  const mem = getUint8Memory0();
  let offset = 0;
  for (; offset < len; offset++) {
    const code = arg.charCodeAt(offset);
    if (code > 127)
      break;
    mem[ptr + offset] = code;
  }
  if (offset !== len) {
    if (offset !== 0) {
      arg = arg.slice(offset);
    }
    ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
    const view = getUint8Memory0().subarray(ptr + offset, ptr + len);
    const ret = encodeString(arg, view);
    offset += ret.written;
    ptr = realloc(ptr, len, offset, 1) >>> 0;
  }
  WASM_VECTOR_LEN = offset;
  return ptr;
}
function isLikeNone(x) {
  return x === void 0 || x === null;
}
function getInt32Memory0() {
  if (cachedInt32Memory0 === null || cachedInt32Memory0.byteLength === 0) {
    cachedInt32Memory0 = new Int32Array(wasm.memory.buffer);
  }
  return cachedInt32Memory0;
}
function getStringFromWasm0(ptr, len) {
  ptr = ptr >>> 0;
  return cachedTextDecoder.decode(getUint8Memory0().subarray(ptr, ptr + len));
}
function _assertClass(instance, klass) {
  if (!(instance instanceof klass)) {
    throw new Error(`expected instance of ${klass.name}`);
  }
  return instance.ptr;
}
function handleError(f, args) {
  try {
    return f.apply(this, args);
  } catch (e) {
    wasm.__wbindgen_exn_store(addHeapObject(e));
  }
}
async function __wbg_load(module, imports) {
  if (typeof Response === "function" && module instanceof Response) {
    if (typeof WebAssembly.instantiateStreaming === "function") {
      try {
        return await WebAssembly.instantiateStreaming(module, imports);
      } catch (e) {
        if (module.headers.get("Content-Type") != "application/wasm") {
          console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);
        } else {
          throw e;
        }
      }
    }
    const bytes = await module.arrayBuffer();
    return await WebAssembly.instantiate(bytes, imports);
  } else {
    const instance = await WebAssembly.instantiate(module, imports);
    if (instance instanceof WebAssembly.Instance) {
      return { instance, module };
    } else {
      return instance;
    }
  }
}
function __wbg_get_imports() {
  const imports = {};
  imports.wbg = {};
  imports.wbg.__wbg_new_28c511d9baebfa89 = function(arg0, arg1) {
    const ret = new Error(getStringFromWasm0(arg0, arg1));
    return addHeapObject(ret);
  };
  imports.wbg.__wbindgen_memory = function() {
    const ret = wasm.memory;
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_buffer_12d079cc21e14bdb = function(arg0) {
    const ret = getObject(arg0).buffer;
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_newwithbyteoffsetandlength_aa4a17c33a06e5cb = function(arg0, arg1, arg2) {
    const ret = new Uint8Array(getObject(arg0), arg1 >>> 0, arg2 >>> 0);
    return addHeapObject(ret);
  };
  imports.wbg.__wbindgen_object_drop_ref = function(arg0) {
    takeObject(arg0);
  };
  imports.wbg.__wbg_new_63b92bc8671ed464 = function(arg0) {
    const ret = new Uint8Array(getObject(arg0));
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_values_839f3396d5aac002 = function(arg0) {
    const ret = getObject(arg0).values();
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_next_196c84450b364254 = function() {
    return handleError(function(arg0) {
      const ret = getObject(arg0).next();
      return addHeapObject(ret);
    }, arguments);
  };
  imports.wbg.__wbg_done_298b57d23c0fc80c = function(arg0) {
    const ret = getObject(arg0).done;
    return ret;
  };
  imports.wbg.__wbg_value_d93c65011f51a456 = function(arg0) {
    const ret = getObject(arg0).value;
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_instanceof_Uint8Array_2b3bbecd033d19f6 = function(arg0) {
    let result;
    try {
      result = getObject(arg0) instanceof Uint8Array;
    } catch (_) {
      result = false;
    }
    const ret = result;
    return ret;
  };
  imports.wbg.__wbindgen_string_get = function(arg0, arg1) {
    const obj = getObject(arg1);
    const ret = typeof obj === "string" ? obj : void 0;
    var ptr1 = isLikeNone(ret) ? 0 : passStringToWasm0(ret, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
    var len1 = WASM_VECTOR_LEN;
    getInt32Memory0()[arg0 / 4 + 1] = len1;
    getInt32Memory0()[arg0 / 4 + 0] = ptr1;
  };
  imports.wbg.__wbg_new_16b304a2cfa7ff4a = function() {
    const ret = new Array();
    return addHeapObject(ret);
  };
  imports.wbg.__wbindgen_string_new = function(arg0, arg1) {
    const ret = getStringFromWasm0(arg0, arg1);
    return addHeapObject(ret);
  };
  imports.wbg.__wbg_push_a5b05aedc7234f9f = function(arg0, arg1) {
    const ret = getObject(arg0).push(getObject(arg1));
    return ret;
  };
  imports.wbg.__wbg_length_c20a40f15020d68a = function(arg0) {
    const ret = getObject(arg0).length;
    return ret;
  };
  imports.wbg.__wbg_set_a47bac70306a19a7 = function(arg0, arg1, arg2) {
    getObject(arg0).set(getObject(arg1), arg2 >>> 0);
  };
  imports.wbg.__wbindgen_throw = function(arg0, arg1) {
    throw new Error(getStringFromWasm0(arg0, arg1));
  };
  return imports;
}
function __wbg_init_memory(imports, maybe_memory) {
}
function __wbg_finalize_init(instance, module) {
  wasm = instance.exports;
  __wbg_init.__wbindgen_wasm_module = module;
  cachedInt32Memory0 = null;
  cachedUint8Memory0 = null;
  return wasm;
}
async function __wbg_init(input) {
  if (wasm !== void 0)
    return wasm;
  if (typeof input === "undefined") {
    input = new URL("index_bg.wasm", void 0);
  }
  const imports = __wbg_get_imports();
  if (typeof input === "string" || typeof Request === "function" && input instanceof Request || typeof URL === "function" && input instanceof URL) {
    input = fetch(input);
  }
  __wbg_init_memory(imports);
  const { instance, module } = await __wbg_load(await input, imports);
  return __wbg_finalize_init(instance, module);
}
function isCustomFontsOptions(value) {
  return Object.prototype.hasOwnProperty.call(value, "fontBuffers");
}
var wasm, heap, heap_next, WASM_VECTOR_LEN, cachedUint8Memory0, cachedTextEncoder, encodeString, cachedInt32Memory0, cachedTextDecoder, BBoxFinalization, BBox, RenderedImageFinalization, RenderedImage, ResvgFinalization, Resvg, dist_default, initialized, initWasm, Resvg2;
var init_resvg_wasm = __esm({
  "node_modules/@resvg/resvg-wasm/index.mjs"() {
    heap = new Array(128).fill(void 0);
    heap.push(void 0, null, true, false);
    heap_next = heap.length;
    WASM_VECTOR_LEN = 0;
    cachedUint8Memory0 = null;
    cachedTextEncoder = typeof TextEncoder !== "undefined" ? new TextEncoder("utf-8") : { encode: () => {
      throw Error("TextEncoder not available");
    } };
    encodeString = typeof cachedTextEncoder.encodeInto === "function" ? function(arg, view) {
      return cachedTextEncoder.encodeInto(arg, view);
    } : function(arg, view) {
      const buf = cachedTextEncoder.encode(arg);
      view.set(buf);
      return {
        read: arg.length,
        written: buf.length
      };
    };
    cachedInt32Memory0 = null;
    cachedTextDecoder = typeof TextDecoder !== "undefined" ? new TextDecoder("utf-8", { ignoreBOM: true, fatal: true }) : { decode: () => {
      throw Error("TextDecoder not available");
    } };
    if (typeof TextDecoder !== "undefined") {
      cachedTextDecoder.decode();
    }
    BBoxFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_bbox_free(ptr >>> 0));
    BBox = class _BBox {
      static __wrap(ptr) {
        ptr = ptr >>> 0;
        const obj = Object.create(_BBox.prototype);
        obj.__wbg_ptr = ptr;
        BBoxFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
      }
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        BBoxFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_bbox_free(ptr);
      }
      /**
      * @returns {number}
      */
      get x() {
        const ret = wasm.__wbg_get_bbox_x(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set x(arg0) {
        wasm.__wbg_set_bbox_x(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get y() {
        const ret = wasm.__wbg_get_bbox_y(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set y(arg0) {
        wasm.__wbg_set_bbox_y(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get width() {
        const ret = wasm.__wbg_get_bbox_width(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set width(arg0) {
        wasm.__wbg_set_bbox_width(this.__wbg_ptr, arg0);
      }
      /**
      * @returns {number}
      */
      get height() {
        const ret = wasm.__wbg_get_bbox_height(this.__wbg_ptr);
        return ret;
      }
      /**
      * @param {number} arg0
      */
      set height(arg0) {
        wasm.__wbg_set_bbox_height(this.__wbg_ptr, arg0);
      }
    };
    RenderedImageFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_renderedimage_free(ptr >>> 0));
    RenderedImage = class _RenderedImage {
      static __wrap(ptr) {
        ptr = ptr >>> 0;
        const obj = Object.create(_RenderedImage.prototype);
        obj.__wbg_ptr = ptr;
        RenderedImageFinalization.register(obj, obj.__wbg_ptr, obj);
        return obj;
      }
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        RenderedImageFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_renderedimage_free(ptr);
      }
      /**
      * Get the PNG width
      * @returns {number}
      */
      get width() {
        const ret = wasm.renderedimage_width(this.__wbg_ptr);
        return ret >>> 0;
      }
      /**
      * Get the PNG height
      * @returns {number}
      */
      get height() {
        const ret = wasm.renderedimage_height(this.__wbg_ptr);
        return ret >>> 0;
      }
      /**
      * Write the image data to Uint8Array
      * @returns {Uint8Array}
      */
      asPng() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.renderedimage_asPng(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return takeObject(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Get the RGBA pixels of the image
      * @returns {Uint8Array}
      */
      get pixels() {
        const ret = wasm.renderedimage_pixels(this.__wbg_ptr);
        return takeObject(ret);
      }
    };
    ResvgFinalization = typeof FinalizationRegistry === "undefined" ? { register: () => {
    }, unregister: () => {
    } } : new FinalizationRegistry((ptr) => wasm.__wbg_resvg_free(ptr >>> 0));
    Resvg = class {
      __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        ResvgFinalization.unregister(this);
        return ptr;
      }
      free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_resvg_free(ptr);
      }
      /**
      * @param {Uint8Array | string} svg
      * @param {string | undefined} [options]
      * @param {Array<any> | undefined} [custom_font_buffers]
      */
      constructor(svg, options, custom_font_buffers) {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          var ptr0 = isLikeNone(options) ? 0 : passStringToWasm0(options, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
          var len0 = WASM_VECTOR_LEN;
          wasm.resvg_new(retptr, addHeapObject(svg), ptr0, len0, isLikeNone(custom_font_buffers) ? 0 : addHeapObject(custom_font_buffers));
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          this.__wbg_ptr = r0 >>> 0;
          return this;
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Get the SVG width
      * @returns {number}
      */
      get width() {
        const ret = wasm.resvg_width(this.__wbg_ptr);
        return ret;
      }
      /**
      * Get the SVG height
      * @returns {number}
      */
      get height() {
        const ret = wasm.resvg_height(this.__wbg_ptr);
        return ret;
      }
      /**
      * Renders an SVG in Wasm
      * @returns {RenderedImage}
      */
      render() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_render(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return RenderedImage.__wrap(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * Output usvg-simplified SVG string
      * @returns {string}
      */
      toString() {
        let deferred1_0;
        let deferred1_1;
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_toString(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          deferred1_0 = r0;
          deferred1_1 = r1;
          return getStringFromWasm0(r0, r1);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
          wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
      }
      /**
      * Calculate a maximum bounding box of all visible elements in this SVG.
      *
      * Note: path bounding box are approx values.
      * @returns {BBox | undefined}
      */
      innerBBox() {
        const ret = wasm.resvg_innerBBox(this.__wbg_ptr);
        return ret === 0 ? void 0 : BBox.__wrap(ret);
      }
      /**
      * Calculate a maximum bounding box of all visible elements in this SVG.
      * This will first apply transform.
      * Similar to `SVGGraphicsElement.getBBox()` DOM API.
      * @returns {BBox | undefined}
      */
      getBBox() {
        const ret = wasm.resvg_getBBox(this.__wbg_ptr);
        return ret === 0 ? void 0 : BBox.__wrap(ret);
      }
      /**
      * Use a given `BBox` to crop the svg. Currently this method simply changes
      * the viewbox/size of the svg and do not move the elements for simplicity
      * @param {BBox} bbox
      */
      cropByBBox(bbox) {
        _assertClass(bbox, BBox);
        wasm.resvg_cropByBBox(this.__wbg_ptr, bbox.__wbg_ptr);
      }
      /**
      * @returns {Array<any>}
      */
      imagesToResolve() {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          wasm.resvg_imagesToResolve(retptr, this.__wbg_ptr);
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          var r2 = getInt32Memory0()[retptr / 4 + 2];
          if (r2) {
            throw takeObject(r1);
          }
          return takeObject(r0);
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
      /**
      * @param {string} href
      * @param {Uint8Array} buffer
      */
      resolveImage(href, buffer2) {
        try {
          const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
          const ptr0 = passStringToWasm0(href, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
          const len0 = WASM_VECTOR_LEN;
          wasm.resvg_resolveImage(retptr, this.__wbg_ptr, ptr0, len0, addHeapObject(buffer2));
          var r0 = getInt32Memory0()[retptr / 4 + 0];
          var r1 = getInt32Memory0()[retptr / 4 + 1];
          if (r1) {
            throw takeObject(r0);
          }
        } finally {
          wasm.__wbindgen_add_to_stack_pointer(16);
        }
      }
    };
    dist_default = __wbg_init;
    initialized = false;
    initWasm = async (module_or_path) => {
      if (initialized) {
        throw new Error("Already initialized. The `initWasm()` function can be used only once.");
      }
      await dist_default(await module_or_path);
      initialized = true;
    };
    Resvg2 = class extends Resvg {
      /**
       * @param {Uint8Array | string} svg
       * @param {ResvgRenderOptions | undefined} options
       */
      constructor(svg, options) {
        if (!initialized)
          throw new Error("Wasm has not been initialized. Call `initWasm()` function.");
        const font = options?.font;
        if (!!font && isCustomFontsOptions(font)) {
          const serializableOptions = {
            ...options,
            font: {
              ...font,
              fontBuffers: void 0
            }
          };
          super(svg, JSON.stringify(serializableOptions), font.fontBuffers);
        } else {
          super(svg, JSON.stringify(options));
        }
      }
    };
  }
});

// node_modules/opentype.js/dist/opentype.js
var require_opentype = __commonJS({
  "node_modules/opentype.js/dist/opentype.js"(exports, module) {
    (function(global, factory) {
      typeof exports === "object" && typeof module !== "undefined" ? factory(exports) : typeof define === "function" && define.amd ? define(["exports"], factory) : (global = global || self, factory(global.opentype = {}));
    })(exports, (function(exports2) {
      "use strict";
      if (!String.prototype.codePointAt) {
        (function() {
          var defineProperty = (function() {
            try {
              var object = {};
              var $defineProperty = Object.defineProperty;
              var result = $defineProperty(object, object, object) && $defineProperty;
            } catch (error) {
            }
            return result;
          })();
          var codePointAt = function(position) {
            if (this == null) {
              throw TypeError();
            }
            var string = String(this);
            var size2 = string.length;
            var index = position ? Number(position) : 0;
            if (index != index) {
              index = 0;
            }
            if (index < 0 || index >= size2) {
              return void 0;
            }
            var first = string.charCodeAt(index);
            var second;
            if (
              // check if it’s the start of a surrogate pair
              first >= 55296 && first <= 56319 && // high surrogate
              size2 > index + 1
            ) {
              second = string.charCodeAt(index + 1);
              if (second >= 56320 && second <= 57343) {
                return (first - 55296) * 1024 + second - 56320 + 65536;
              }
            }
            return first;
          };
          if (defineProperty) {
            defineProperty(String.prototype, "codePointAt", {
              "value": codePointAt,
              "configurable": true,
              "writable": true
            });
          } else {
            String.prototype.codePointAt = codePointAt;
          }
        })();
      }
      var TINF_OK = 0;
      var TINF_DATA_ERROR = -3;
      function Tree() {
        this.table = new Uint16Array(16);
        this.trans = new Uint16Array(288);
      }
      function Data(source, dest) {
        this.source = source;
        this.sourceIndex = 0;
        this.tag = 0;
        this.bitcount = 0;
        this.dest = dest;
        this.destLen = 0;
        this.ltree = new Tree();
        this.dtree = new Tree();
      }
      var sltree = new Tree();
      var sdtree = new Tree();
      var length_bits = new Uint8Array(30);
      var length_base = new Uint16Array(30);
      var dist_bits = new Uint8Array(30);
      var dist_base = new Uint16Array(30);
      var clcidx = new Uint8Array([
        16,
        17,
        18,
        0,
        8,
        7,
        9,
        6,
        10,
        5,
        11,
        4,
        12,
        3,
        13,
        2,
        14,
        1,
        15
      ]);
      var code_tree = new Tree();
      var lengths = new Uint8Array(288 + 32);
      function tinf_build_bits_base(bits, base, delta, first) {
        var i, sum;
        for (i = 0; i < delta; ++i) {
          bits[i] = 0;
        }
        for (i = 0; i < 30 - delta; ++i) {
          bits[i + delta] = i / delta | 0;
        }
        for (sum = first, i = 0; i < 30; ++i) {
          base[i] = sum;
          sum += 1 << bits[i];
        }
      }
      function tinf_build_fixed_trees(lt, dt) {
        var i;
        for (i = 0; i < 7; ++i) {
          lt.table[i] = 0;
        }
        lt.table[7] = 24;
        lt.table[8] = 152;
        lt.table[9] = 112;
        for (i = 0; i < 24; ++i) {
          lt.trans[i] = 256 + i;
        }
        for (i = 0; i < 144; ++i) {
          lt.trans[24 + i] = i;
        }
        for (i = 0; i < 8; ++i) {
          lt.trans[24 + 144 + i] = 280 + i;
        }
        for (i = 0; i < 112; ++i) {
          lt.trans[24 + 144 + 8 + i] = 144 + i;
        }
        for (i = 0; i < 5; ++i) {
          dt.table[i] = 0;
        }
        dt.table[5] = 32;
        for (i = 0; i < 32; ++i) {
          dt.trans[i] = i;
        }
      }
      var offs = new Uint16Array(16);
      function tinf_build_tree(t, lengths2, off, num2) {
        var i, sum;
        for (i = 0; i < 16; ++i) {
          t.table[i] = 0;
        }
        for (i = 0; i < num2; ++i) {
          t.table[lengths2[off + i]]++;
        }
        t.table[0] = 0;
        for (sum = 0, i = 0; i < 16; ++i) {
          offs[i] = sum;
          sum += t.table[i];
        }
        for (i = 0; i < num2; ++i) {
          if (lengths2[off + i]) {
            t.trans[offs[lengths2[off + i]]++] = i;
          }
        }
      }
      function tinf_getbit(d) {
        if (!d.bitcount--) {
          d.tag = d.source[d.sourceIndex++];
          d.bitcount = 7;
        }
        var bit = d.tag & 1;
        d.tag >>>= 1;
        return bit;
      }
      function tinf_read_bits(d, num2, base) {
        if (!num2) {
          return base;
        }
        while (d.bitcount < 24) {
          d.tag |= d.source[d.sourceIndex++] << d.bitcount;
          d.bitcount += 8;
        }
        var val = d.tag & 65535 >>> 16 - num2;
        d.tag >>>= num2;
        d.bitcount -= num2;
        return val + base;
      }
      function tinf_decode_symbol(d, t) {
        while (d.bitcount < 24) {
          d.tag |= d.source[d.sourceIndex++] << d.bitcount;
          d.bitcount += 8;
        }
        var sum = 0, cur = 0, len = 0;
        var tag = d.tag;
        do {
          cur = 2 * cur + (tag & 1);
          tag >>>= 1;
          ++len;
          sum += t.table[len];
          cur -= t.table[len];
        } while (cur >= 0);
        d.tag = tag;
        d.bitcount -= len;
        return t.trans[sum + cur];
      }
      function tinf_decode_trees(d, lt, dt) {
        var hlit, hdist, hclen;
        var i, num2, length;
        hlit = tinf_read_bits(d, 5, 257);
        hdist = tinf_read_bits(d, 5, 1);
        hclen = tinf_read_bits(d, 4, 4);
        for (i = 0; i < 19; ++i) {
          lengths[i] = 0;
        }
        for (i = 0; i < hclen; ++i) {
          var clen = tinf_read_bits(d, 3, 0);
          lengths[clcidx[i]] = clen;
        }
        tinf_build_tree(code_tree, lengths, 0, 19);
        for (num2 = 0; num2 < hlit + hdist; ) {
          var sym = tinf_decode_symbol(d, code_tree);
          switch (sym) {
            case 16:
              var prev = lengths[num2 - 1];
              for (length = tinf_read_bits(d, 2, 3); length; --length) {
                lengths[num2++] = prev;
              }
              break;
            case 17:
              for (length = tinf_read_bits(d, 3, 3); length; --length) {
                lengths[num2++] = 0;
              }
              break;
            case 18:
              for (length = tinf_read_bits(d, 7, 11); length; --length) {
                lengths[num2++] = 0;
              }
              break;
            default:
              lengths[num2++] = sym;
              break;
          }
        }
        tinf_build_tree(lt, lengths, 0, hlit);
        tinf_build_tree(dt, lengths, hlit, hdist);
      }
      function tinf_inflate_block_data(d, lt, dt) {
        while (1) {
          var sym = tinf_decode_symbol(d, lt);
          if (sym === 256) {
            return TINF_OK;
          }
          if (sym < 256) {
            d.dest[d.destLen++] = sym;
          } else {
            var length, dist, offs2;
            var i;
            sym -= 257;
            length = tinf_read_bits(d, length_bits[sym], length_base[sym]);
            dist = tinf_decode_symbol(d, dt);
            offs2 = d.destLen - tinf_read_bits(d, dist_bits[dist], dist_base[dist]);
            for (i = offs2; i < offs2 + length; ++i) {
              d.dest[d.destLen++] = d.dest[i];
            }
          }
        }
      }
      function tinf_inflate_uncompressed_block(d) {
        var length, invlength;
        var i;
        while (d.bitcount > 8) {
          d.sourceIndex--;
          d.bitcount -= 8;
        }
        length = d.source[d.sourceIndex + 1];
        length = 256 * length + d.source[d.sourceIndex];
        invlength = d.source[d.sourceIndex + 3];
        invlength = 256 * invlength + d.source[d.sourceIndex + 2];
        if (length !== (~invlength & 65535)) {
          return TINF_DATA_ERROR;
        }
        d.sourceIndex += 4;
        for (i = length; i; --i) {
          d.dest[d.destLen++] = d.source[d.sourceIndex++];
        }
        d.bitcount = 0;
        return TINF_OK;
      }
      function tinf_uncompress(source, dest) {
        var d = new Data(source, dest);
        var bfinal, btype, res;
        do {
          bfinal = tinf_getbit(d);
          btype = tinf_read_bits(d, 2, 0);
          switch (btype) {
            case 0:
              res = tinf_inflate_uncompressed_block(d);
              break;
            case 1:
              res = tinf_inflate_block_data(d, sltree, sdtree);
              break;
            case 2:
              tinf_decode_trees(d, d.ltree, d.dtree);
              res = tinf_inflate_block_data(d, d.ltree, d.dtree);
              break;
            default:
              res = TINF_DATA_ERROR;
          }
          if (res !== TINF_OK) {
            throw new Error("Data error");
          }
        } while (!bfinal);
        if (d.destLen < d.dest.length) {
          if (typeof d.dest.slice === "function") {
            return d.dest.slice(0, d.destLen);
          } else {
            return d.dest.subarray(0, d.destLen);
          }
        }
        return d.dest;
      }
      tinf_build_fixed_trees(sltree, sdtree);
      tinf_build_bits_base(length_bits, length_base, 4, 3);
      tinf_build_bits_base(dist_bits, dist_base, 2, 1);
      length_bits[28] = 0;
      length_base[28] = 258;
      var tinyInflate = tinf_uncompress;
      function derive(v0, v1, v2, v3, t) {
        return Math.pow(1 - t, 3) * v0 + 3 * Math.pow(1 - t, 2) * t * v1 + 3 * (1 - t) * Math.pow(t, 2) * v2 + Math.pow(t, 3) * v3;
      }
      function BoundingBox() {
        this.x1 = Number.NaN;
        this.y1 = Number.NaN;
        this.x2 = Number.NaN;
        this.y2 = Number.NaN;
      }
      BoundingBox.prototype.isEmpty = function() {
        return isNaN(this.x1) || isNaN(this.y1) || isNaN(this.x2) || isNaN(this.y2);
      };
      BoundingBox.prototype.addPoint = function(x, y) {
        if (typeof x === "number") {
          if (isNaN(this.x1) || isNaN(this.x2)) {
            this.x1 = x;
            this.x2 = x;
          }
          if (x < this.x1) {
            this.x1 = x;
          }
          if (x > this.x2) {
            this.x2 = x;
          }
        }
        if (typeof y === "number") {
          if (isNaN(this.y1) || isNaN(this.y2)) {
            this.y1 = y;
            this.y2 = y;
          }
          if (y < this.y1) {
            this.y1 = y;
          }
          if (y > this.y2) {
            this.y2 = y;
          }
        }
      };
      BoundingBox.prototype.addX = function(x) {
        this.addPoint(x, null);
      };
      BoundingBox.prototype.addY = function(y) {
        this.addPoint(null, y);
      };
      BoundingBox.prototype.addBezier = function(x0, y0, x1, y1, x2, y2, x, y) {
        var p0 = [x0, y0];
        var p1 = [x1, y1];
        var p2 = [x2, y2];
        var p3 = [x, y];
        this.addPoint(x0, y0);
        this.addPoint(x, y);
        for (var i = 0; i <= 1; i++) {
          var b2 = 6 * p0[i] - 12 * p1[i] + 6 * p2[i];
          var a = -3 * p0[i] + 9 * p1[i] - 9 * p2[i] + 3 * p3[i];
          var c = 3 * p1[i] - 3 * p0[i];
          if (a === 0) {
            if (b2 === 0) {
              continue;
            }
            var t = -c / b2;
            if (0 < t && t < 1) {
              if (i === 0) {
                this.addX(derive(p0[i], p1[i], p2[i], p3[i], t));
              }
              if (i === 1) {
                this.addY(derive(p0[i], p1[i], p2[i], p3[i], t));
              }
            }
            continue;
          }
          var b2ac = Math.pow(b2, 2) - 4 * c * a;
          if (b2ac < 0) {
            continue;
          }
          var t1 = (-b2 + Math.sqrt(b2ac)) / (2 * a);
          if (0 < t1 && t1 < 1) {
            if (i === 0) {
              this.addX(derive(p0[i], p1[i], p2[i], p3[i], t1));
            }
            if (i === 1) {
              this.addY(derive(p0[i], p1[i], p2[i], p3[i], t1));
            }
          }
          var t2 = (-b2 - Math.sqrt(b2ac)) / (2 * a);
          if (0 < t2 && t2 < 1) {
            if (i === 0) {
              this.addX(derive(p0[i], p1[i], p2[i], p3[i], t2));
            }
            if (i === 1) {
              this.addY(derive(p0[i], p1[i], p2[i], p3[i], t2));
            }
          }
        }
      };
      BoundingBox.prototype.addQuad = function(x0, y0, x1, y1, x, y) {
        var cp1x = x0 + 2 / 3 * (x1 - x0);
        var cp1y = y0 + 2 / 3 * (y1 - y0);
        var cp2x = cp1x + 1 / 3 * (x - x0);
        var cp2y = cp1y + 1 / 3 * (y - y0);
        this.addBezier(x0, y0, cp1x, cp1y, cp2x, cp2y, x, y);
      };
      function Path() {
        this.commands = [];
        this.fill = "black";
        this.stroke = null;
        this.strokeWidth = 1;
      }
      Path.prototype.moveTo = function(x, y) {
        this.commands.push({
          type: "M",
          x,
          y
        });
      };
      Path.prototype.lineTo = function(x, y) {
        this.commands.push({
          type: "L",
          x,
          y
        });
      };
      Path.prototype.curveTo = Path.prototype.bezierCurveTo = function(x1, y1, x2, y2, x, y) {
        this.commands.push({
          type: "C",
          x1,
          y1,
          x2,
          y2,
          x,
          y
        });
      };
      Path.prototype.quadTo = Path.prototype.quadraticCurveTo = function(x1, y1, x, y) {
        this.commands.push({
          type: "Q",
          x1,
          y1,
          x,
          y
        });
      };
      Path.prototype.close = Path.prototype.closePath = function() {
        this.commands.push({
          type: "Z"
        });
      };
      Path.prototype.extend = function(pathOrCommands) {
        if (pathOrCommands.commands) {
          pathOrCommands = pathOrCommands.commands;
        } else if (pathOrCommands instanceof BoundingBox) {
          var box = pathOrCommands;
          this.moveTo(box.x1, box.y1);
          this.lineTo(box.x2, box.y1);
          this.lineTo(box.x2, box.y2);
          this.lineTo(box.x1, box.y2);
          this.close();
          return;
        }
        Array.prototype.push.apply(this.commands, pathOrCommands);
      };
      Path.prototype.getBoundingBox = function() {
        var box = new BoundingBox();
        var startX = 0;
        var startY = 0;
        var prevX = 0;
        var prevY = 0;
        for (var i = 0; i < this.commands.length; i++) {
          var cmd = this.commands[i];
          switch (cmd.type) {
            case "M":
              box.addPoint(cmd.x, cmd.y);
              startX = prevX = cmd.x;
              startY = prevY = cmd.y;
              break;
            case "L":
              box.addPoint(cmd.x, cmd.y);
              prevX = cmd.x;
              prevY = cmd.y;
              break;
            case "Q":
              box.addQuad(prevX, prevY, cmd.x1, cmd.y1, cmd.x, cmd.y);
              prevX = cmd.x;
              prevY = cmd.y;
              break;
            case "C":
              box.addBezier(prevX, prevY, cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.x, cmd.y);
              prevX = cmd.x;
              prevY = cmd.y;
              break;
            case "Z":
              prevX = startX;
              prevY = startY;
              break;
            default:
              throw new Error("Unexpected path command " + cmd.type);
          }
        }
        if (box.isEmpty()) {
          box.addPoint(0, 0);
        }
        return box;
      };
      Path.prototype.draw = function(ctx) {
        ctx.beginPath();
        for (var i = 0; i < this.commands.length; i += 1) {
          var cmd = this.commands[i];
          if (cmd.type === "M") {
            ctx.moveTo(cmd.x, cmd.y);
          } else if (cmd.type === "L") {
            ctx.lineTo(cmd.x, cmd.y);
          } else if (cmd.type === "C") {
            ctx.bezierCurveTo(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.x, cmd.y);
          } else if (cmd.type === "Q") {
            ctx.quadraticCurveTo(cmd.x1, cmd.y1, cmd.x, cmd.y);
          } else if (cmd.type === "Z") {
            ctx.closePath();
          }
        }
        if (this.fill) {
          ctx.fillStyle = this.fill;
          ctx.fill();
        }
        if (this.stroke) {
          ctx.strokeStyle = this.stroke;
          ctx.lineWidth = this.strokeWidth;
          ctx.stroke();
        }
      };
      Path.prototype.toPathData = function(decimalPlaces) {
        decimalPlaces = decimalPlaces !== void 0 ? decimalPlaces : 2;
        function floatToString(v) {
          if (Math.round(v) === v) {
            return "" + Math.round(v);
          } else {
            return v.toFixed(decimalPlaces);
          }
        }
        function packValues() {
          var arguments$1 = arguments;
          var s = "";
          for (var i2 = 0; i2 < arguments.length; i2 += 1) {
            var v = arguments$1[i2];
            if (v >= 0 && i2 > 0) {
              s += " ";
            }
            s += floatToString(v);
          }
          return s;
        }
        var d = "";
        for (var i = 0; i < this.commands.length; i += 1) {
          var cmd = this.commands[i];
          if (cmd.type === "M") {
            d += "M" + packValues(cmd.x, cmd.y);
          } else if (cmd.type === "L") {
            d += "L" + packValues(cmd.x, cmd.y);
          } else if (cmd.type === "C") {
            d += "C" + packValues(cmd.x1, cmd.y1, cmd.x2, cmd.y2, cmd.x, cmd.y);
          } else if (cmd.type === "Q") {
            d += "Q" + packValues(cmd.x1, cmd.y1, cmd.x, cmd.y);
          } else if (cmd.type === "Z") {
            d += "Z";
          }
        }
        return d;
      };
      Path.prototype.toSVG = function(decimalPlaces) {
        var svg = '<path d="';
        svg += this.toPathData(decimalPlaces);
        svg += '"';
        if (this.fill && this.fill !== "black") {
          if (this.fill === null) {
            svg += ' fill="none"';
          } else {
            svg += ' fill="' + this.fill + '"';
          }
        }
        if (this.stroke) {
          svg += ' stroke="' + this.stroke + '" stroke-width="' + this.strokeWidth + '"';
        }
        svg += "/>";
        return svg;
      };
      Path.prototype.toDOMElement = function(decimalPlaces) {
        var temporaryPath = this.toPathData(decimalPlaces);
        var newPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
        newPath.setAttribute("d", temporaryPath);
        return newPath;
      };
      function fail(message) {
        throw new Error(message);
      }
      function argument(predicate, message) {
        if (!predicate) {
          fail(message);
        }
      }
      var check = { fail, argument, assert: argument };
      var LIMIT16 = 32768;
      var LIMIT32 = 2147483648;
      var decode = {};
      var encode = {};
      var sizeOf = {};
      function constant(v) {
        return function() {
          return v;
        };
      }
      encode.BYTE = function(v) {
        check.argument(v >= 0 && v <= 255, "Byte value should be between 0 and 255.");
        return [v];
      };
      sizeOf.BYTE = constant(1);
      encode.CHAR = function(v) {
        return [v.charCodeAt(0)];
      };
      sizeOf.CHAR = constant(1);
      encode.CHARARRAY = function(v) {
        if (typeof v === "undefined") {
          v = "";
          console.warn("Undefined CHARARRAY encountered and treated as an empty string. This is probably caused by a missing glyph name.");
        }
        var b2 = [];
        for (var i = 0; i < v.length; i += 1) {
          b2[i] = v.charCodeAt(i);
        }
        return b2;
      };
      sizeOf.CHARARRAY = function(v) {
        if (typeof v === "undefined") {
          return 0;
        }
        return v.length;
      };
      encode.USHORT = function(v) {
        return [v >> 8 & 255, v & 255];
      };
      sizeOf.USHORT = constant(2);
      encode.SHORT = function(v) {
        if (v >= LIMIT16) {
          v = -(2 * LIMIT16 - v);
        }
        return [v >> 8 & 255, v & 255];
      };
      sizeOf.SHORT = constant(2);
      encode.UINT24 = function(v) {
        return [v >> 16 & 255, v >> 8 & 255, v & 255];
      };
      sizeOf.UINT24 = constant(3);
      encode.ULONG = function(v) {
        return [v >> 24 & 255, v >> 16 & 255, v >> 8 & 255, v & 255];
      };
      sizeOf.ULONG = constant(4);
      encode.LONG = function(v) {
        if (v >= LIMIT32) {
          v = -(2 * LIMIT32 - v);
        }
        return [v >> 24 & 255, v >> 16 & 255, v >> 8 & 255, v & 255];
      };
      sizeOf.LONG = constant(4);
      encode.FIXED = encode.ULONG;
      sizeOf.FIXED = sizeOf.ULONG;
      encode.FWORD = encode.SHORT;
      sizeOf.FWORD = sizeOf.SHORT;
      encode.UFWORD = encode.USHORT;
      sizeOf.UFWORD = sizeOf.USHORT;
      encode.LONGDATETIME = function(v) {
        return [0, 0, 0, 0, v >> 24 & 255, v >> 16 & 255, v >> 8 & 255, v & 255];
      };
      sizeOf.LONGDATETIME = constant(8);
      encode.TAG = function(v) {
        check.argument(v.length === 4, "Tag should be exactly 4 ASCII characters.");
        return [
          v.charCodeAt(0),
          v.charCodeAt(1),
          v.charCodeAt(2),
          v.charCodeAt(3)
        ];
      };
      sizeOf.TAG = constant(4);
      encode.Card8 = encode.BYTE;
      sizeOf.Card8 = sizeOf.BYTE;
      encode.Card16 = encode.USHORT;
      sizeOf.Card16 = sizeOf.USHORT;
      encode.OffSize = encode.BYTE;
      sizeOf.OffSize = sizeOf.BYTE;
      encode.SID = encode.USHORT;
      sizeOf.SID = sizeOf.USHORT;
      encode.NUMBER = function(v) {
        if (v >= -107 && v <= 107) {
          return [v + 139];
        } else if (v >= 108 && v <= 1131) {
          v = v - 108;
          return [(v >> 8) + 247, v & 255];
        } else if (v >= -1131 && v <= -108) {
          v = -v - 108;
          return [(v >> 8) + 251, v & 255];
        } else if (v >= -32768 && v <= 32767) {
          return encode.NUMBER16(v);
        } else {
          return encode.NUMBER32(v);
        }
      };
      sizeOf.NUMBER = function(v) {
        return encode.NUMBER(v).length;
      };
      encode.NUMBER16 = function(v) {
        return [28, v >> 8 & 255, v & 255];
      };
      sizeOf.NUMBER16 = constant(3);
      encode.NUMBER32 = function(v) {
        return [29, v >> 24 & 255, v >> 16 & 255, v >> 8 & 255, v & 255];
      };
      sizeOf.NUMBER32 = constant(5);
      encode.REAL = function(v) {
        var value = v.toString();
        var m = /\.(\d*?)(?:9{5,20}|0{5,20})\d{0,2}(?:e(.+)|$)/.exec(value);
        if (m) {
          var epsilon = parseFloat("1e" + ((m[2] ? +m[2] : 0) + m[1].length));
          value = (Math.round(v * epsilon) / epsilon).toString();
        }
        var nibbles = "";
        for (var i = 0, ii = value.length; i < ii; i += 1) {
          var c = value[i];
          if (c === "e") {
            nibbles += value[++i] === "-" ? "c" : "b";
          } else if (c === ".") {
            nibbles += "a";
          } else if (c === "-") {
            nibbles += "e";
          } else {
            nibbles += c;
          }
        }
        nibbles += nibbles.length & 1 ? "f" : "ff";
        var out = [30];
        for (var i$1 = 0, ii$1 = nibbles.length; i$1 < ii$1; i$1 += 2) {
          out.push(parseInt(nibbles.substr(i$1, 2), 16));
        }
        return out;
      };
      sizeOf.REAL = function(v) {
        return encode.REAL(v).length;
      };
      encode.NAME = encode.CHARARRAY;
      sizeOf.NAME = sizeOf.CHARARRAY;
      encode.STRING = encode.CHARARRAY;
      sizeOf.STRING = sizeOf.CHARARRAY;
      decode.UTF8 = function(data, offset, numBytes) {
        var codePoints = [];
        var numChars = numBytes;
        for (var j = 0; j < numChars; j++, offset += 1) {
          codePoints[j] = data.getUint8(offset);
        }
        return String.fromCharCode.apply(null, codePoints);
      };
      decode.UTF16 = function(data, offset, numBytes) {
        var codePoints = [];
        var numChars = numBytes / 2;
        for (var j = 0; j < numChars; j++, offset += 2) {
          codePoints[j] = data.getUint16(offset);
        }
        return String.fromCharCode.apply(null, codePoints);
      };
      encode.UTF16 = function(v) {
        var b2 = [];
        for (var i = 0; i < v.length; i += 1) {
          var codepoint = v.charCodeAt(i);
          b2[b2.length] = codepoint >> 8 & 255;
          b2[b2.length] = codepoint & 255;
        }
        return b2;
      };
      sizeOf.UTF16 = function(v) {
        return v.length * 2;
      };
      var eightBitMacEncodings = {
        "x-mac-croatian": (
          // Python: 'mac_croatian'
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\u2020\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\u0160\u2122\xB4\xA8\u2260\u017D\xD8\u221E\xB1\u2264\u2265\u2206\xB5\u2202\u2211\u220F\u0161\u222B\xAA\xBA\u03A9\u017E\xF8\xBF\xA1\xAC\u221A\u0192\u2248\u0106\xAB\u010C\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u0110\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\uF8FF\xA9\u2044\u20AC\u2039\u203A\xC6\xBB\u2013\xB7\u201A\u201E\u2030\xC2\u0107\xC1\u010D\xC8\xCD\xCE\xCF\xCC\xD3\xD4\u0111\xD2\xDA\xDB\xD9\u0131\u02C6\u02DC\xAF\u03C0\xCB\u02DA\xB8\xCA\xE6\u02C7"
        ),
        "x-mac-cyrillic": (
          // Python: 'mac_cyrillic'
          "\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419\u041A\u041B\u041C\u041D\u041E\u041F\u0420\u0421\u0422\u0423\u0424\u0425\u0426\u0427\u0428\u0429\u042A\u042B\u042C\u042D\u042E\u042F\u2020\xB0\u0490\xA3\xA7\u2022\xB6\u0406\xAE\xA9\u2122\u0402\u0452\u2260\u0403\u0453\u221E\xB1\u2264\u2265\u0456\xB5\u0491\u0408\u0404\u0454\u0407\u0457\u0409\u0459\u040A\u045A\u0458\u0405\xAC\u221A\u0192\u2248\u2206\xAB\xBB\u2026\xA0\u040B\u045B\u040C\u045C\u0455\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u201E\u040E\u045E\u040F\u045F\u2116\u0401\u0451\u044F\u0430\u0431\u0432\u0433\u0434\u0435\u0436\u0437\u0438\u0439\u043A\u043B\u043C\u043D\u043E\u043F\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044A\u044B\u044C\u044D\u044E"
        ),
        "x-mac-gaelic": (
          // http://unicode.org/Public/MAPPINGS/VENDORS/APPLE/GAELIC.TXT
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\u2020\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\xB4\xA8\u2260\xC6\xD8\u1E02\xB1\u2264\u2265\u1E03\u010A\u010B\u1E0A\u1E0B\u1E1E\u1E1F\u0120\u0121\u1E40\xE6\xF8\u1E41\u1E56\u1E57\u027C\u0192\u017F\u1E60\xAB\xBB\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u2013\u2014\u201C\u201D\u2018\u2019\u1E61\u1E9B\xFF\u0178\u1E6A\u20AC\u2039\u203A\u0176\u0177\u1E6B\xB7\u1EF2\u1EF3\u204A\xC2\xCA\xC1\xCB\xC8\xCD\xCE\xCF\xCC\xD3\xD4\u2663\xD2\xDA\xDB\xD9\u0131\xDD\xFD\u0174\u0175\u1E84\u1E85\u1E80\u1E81\u1E82\u1E83"
        ),
        "x-mac-greek": (
          // Python: 'mac_greek'
          "\xC4\xB9\xB2\xC9\xB3\xD6\xDC\u0385\xE0\xE2\xE4\u0384\xA8\xE7\xE9\xE8\xEA\xEB\xA3\u2122\xEE\xEF\u2022\xBD\u2030\xF4\xF6\xA6\u20AC\xF9\xFB\xFC\u2020\u0393\u0394\u0398\u039B\u039E\u03A0\xDF\xAE\xA9\u03A3\u03AA\xA7\u2260\xB0\xB7\u0391\xB1\u2264\u2265\xA5\u0392\u0395\u0396\u0397\u0399\u039A\u039C\u03A6\u03AB\u03A8\u03A9\u03AC\u039D\xAC\u039F\u03A1\u2248\u03A4\xAB\xBB\u2026\xA0\u03A5\u03A7\u0386\u0388\u0153\u2013\u2015\u201C\u201D\u2018\u2019\xF7\u0389\u038A\u038C\u038E\u03AD\u03AE\u03AF\u03CC\u038F\u03CD\u03B1\u03B2\u03C8\u03B4\u03B5\u03C6\u03B3\u03B7\u03B9\u03BE\u03BA\u03BB\u03BC\u03BD\u03BF\u03C0\u03CE\u03C1\u03C3\u03C4\u03B8\u03C9\u03C2\u03C7\u03C5\u03B6\u03CA\u03CB\u0390\u03B0\xAD"
        ),
        "x-mac-icelandic": (
          // Python: 'mac_iceland'
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\xDD\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\xB4\xA8\u2260\xC6\xD8\u221E\xB1\u2264\u2265\xA5\xB5\u2202\u2211\u220F\u03C0\u222B\xAA\xBA\u03A9\xE6\xF8\xBF\xA1\xAC\u221A\u0192\u2248\u2206\xAB\xBB\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\xFF\u0178\u2044\u20AC\xD0\xF0\xDE\xFE\xFD\xB7\u201A\u201E\u2030\xC2\xCA\xC1\xCB\xC8\xCD\xCE\xCF\xCC\xD3\xD4\uF8FF\xD2\xDA\xDB\xD9\u0131\u02C6\u02DC\xAF\u02D8\u02D9\u02DA\xB8\u02DD\u02DB\u02C7"
        ),
        "x-mac-inuit": (
          // http://unicode.org/Public/MAPPINGS/VENDORS/APPLE/INUIT.TXT
          "\u1403\u1404\u1405\u1406\u140A\u140B\u1431\u1432\u1433\u1434\u1438\u1439\u1449\u144E\u144F\u1450\u1451\u1455\u1456\u1466\u146D\u146E\u146F\u1470\u1472\u1473\u1483\u148B\u148C\u148D\u148E\u1490\u1491\xB0\u14A1\u14A5\u14A6\u2022\xB6\u14A7\xAE\xA9\u2122\u14A8\u14AA\u14AB\u14BB\u14C2\u14C3\u14C4\u14C5\u14C7\u14C8\u14D0\u14EF\u14F0\u14F1\u14F2\u14F4\u14F5\u1505\u14D5\u14D6\u14D7\u14D8\u14DA\u14DB\u14EA\u1528\u1529\u152A\u152B\u152D\u2026\xA0\u152E\u153E\u1555\u1556\u1557\u2013\u2014\u201C\u201D\u2018\u2019\u1558\u1559\u155A\u155D\u1546\u1547\u1548\u1549\u154B\u154C\u1550\u157F\u1580\u1581\u1582\u1583\u1584\u1585\u158F\u1590\u1591\u1592\u1593\u1594\u1595\u1671\u1672\u1673\u1674\u1675\u1676\u1596\u15A0\u15A1\u15A2\u15A3\u15A4\u15A5\u15A6\u157C\u0141\u0142"
        ),
        "x-mac-ce": (
          // Python: 'mac_latin2'
          "\xC4\u0100\u0101\xC9\u0104\xD6\xDC\xE1\u0105\u010C\xE4\u010D\u0106\u0107\xE9\u0179\u017A\u010E\xED\u010F\u0112\u0113\u0116\xF3\u0117\xF4\xF6\xF5\xFA\u011A\u011B\xFC\u2020\xB0\u0118\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\u0119\xA8\u2260\u0123\u012E\u012F\u012A\u2264\u2265\u012B\u0136\u2202\u2211\u0142\u013B\u013C\u013D\u013E\u0139\u013A\u0145\u0146\u0143\xAC\u221A\u0144\u0147\u2206\xAB\xBB\u2026\xA0\u0148\u0150\xD5\u0151\u014C\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\u014D\u0154\u0155\u0158\u2039\u203A\u0159\u0156\u0157\u0160\u201A\u201E\u0161\u015A\u015B\xC1\u0164\u0165\xCD\u017D\u017E\u016A\xD3\xD4\u016B\u016E\xDA\u016F\u0170\u0171\u0172\u0173\xDD\xFD\u0137\u017B\u0141\u017C\u0122\u02C7"
        ),
        macintosh: (
          // Python: 'mac_roman'
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\u2020\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\xB4\xA8\u2260\xC6\xD8\u221E\xB1\u2264\u2265\xA5\xB5\u2202\u2211\u220F\u03C0\u222B\xAA\xBA\u03A9\xE6\xF8\xBF\xA1\xAC\u221A\u0192\u2248\u2206\xAB\xBB\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\xFF\u0178\u2044\u20AC\u2039\u203A\uFB01\uFB02\u2021\xB7\u201A\u201E\u2030\xC2\xCA\xC1\xCB\xC8\xCD\xCE\xCF\xCC\xD3\xD4\uF8FF\xD2\xDA\xDB\xD9\u0131\u02C6\u02DC\xAF\u02D8\u02D9\u02DA\xB8\u02DD\u02DB\u02C7"
        ),
        "x-mac-romanian": (
          // Python: 'mac_romanian'
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\u2020\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\xB4\xA8\u2260\u0102\u0218\u221E\xB1\u2264\u2265\xA5\xB5\u2202\u2211\u220F\u03C0\u222B\xAA\xBA\u03A9\u0103\u0219\xBF\xA1\xAC\u221A\u0192\u2248\u2206\xAB\xBB\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\xFF\u0178\u2044\u20AC\u2039\u203A\u021A\u021B\u2021\xB7\u201A\u201E\u2030\xC2\xCA\xC1\xCB\xC8\xCD\xCE\xCF\xCC\xD3\xD4\uF8FF\xD2\xDA\xDB\xD9\u0131\u02C6\u02DC\xAF\u02D8\u02D9\u02DA\xB8\u02DD\u02DB\u02C7"
        ),
        "x-mac-turkish": (
          // Python: 'mac_turkish'
          "\xC4\xC5\xC7\xC9\xD1\xD6\xDC\xE1\xE0\xE2\xE4\xE3\xE5\xE7\xE9\xE8\xEA\xEB\xED\xEC\xEE\xEF\xF1\xF3\xF2\xF4\xF6\xF5\xFA\xF9\xFB\xFC\u2020\xB0\xA2\xA3\xA7\u2022\xB6\xDF\xAE\xA9\u2122\xB4\xA8\u2260\xC6\xD8\u221E\xB1\u2264\u2265\xA5\xB5\u2202\u2211\u220F\u03C0\u222B\xAA\xBA\u03A9\xE6\xF8\xBF\xA1\xAC\u221A\u0192\u2248\u2206\xAB\xBB\u2026\xA0\xC0\xC3\xD5\u0152\u0153\u2013\u2014\u201C\u201D\u2018\u2019\xF7\u25CA\xFF\u0178\u011E\u011F\u0130\u0131\u015E\u015F\u2021\xB7\u201A\u201E\u2030\xC2\xCA\xC1\xCB\xC8\xCD\xCE\xCF\xCC\xD3\xD4\uF8FF\xD2\xDA\xDB\xD9\uF8A0\u02C6\u02DC\xAF\u02D8\u02D9\u02DA\xB8\u02DD\u02DB\u02C7"
        )
      };
      decode.MACSTRING = function(dataView, offset, dataLength, encoding) {
        var table3 = eightBitMacEncodings[encoding];
        if (table3 === void 0) {
          return void 0;
        }
        var result = "";
        for (var i = 0; i < dataLength; i++) {
          var c = dataView.getUint8(offset + i);
          if (c <= 127) {
            result += String.fromCharCode(c);
          } else {
            result += table3[c & 127];
          }
        }
        return result;
      };
      var macEncodingTableCache = typeof WeakMap === "function" && /* @__PURE__ */ new WeakMap();
      var macEncodingCacheKeys;
      var getMacEncodingTable = function(encoding) {
        if (!macEncodingCacheKeys) {
          macEncodingCacheKeys = {};
          for (var e in eightBitMacEncodings) {
            macEncodingCacheKeys[e] = new String(e);
          }
        }
        var cacheKey = macEncodingCacheKeys[encoding];
        if (cacheKey === void 0) {
          return void 0;
        }
        if (macEncodingTableCache) {
          var cachedTable = macEncodingTableCache.get(cacheKey);
          if (cachedTable !== void 0) {
            return cachedTable;
          }
        }
        var decodingTable = eightBitMacEncodings[encoding];
        if (decodingTable === void 0) {
          return void 0;
        }
        var encodingTable = {};
        for (var i = 0; i < decodingTable.length; i++) {
          encodingTable[decodingTable.charCodeAt(i)] = i + 128;
        }
        if (macEncodingTableCache) {
          macEncodingTableCache.set(cacheKey, encodingTable);
        }
        return encodingTable;
      };
      encode.MACSTRING = function(str, encoding) {
        var table3 = getMacEncodingTable(encoding);
        if (table3 === void 0) {
          return void 0;
        }
        var result = [];
        for (var i = 0; i < str.length; i++) {
          var c = str.charCodeAt(i);
          if (c >= 128) {
            c = table3[c];
            if (c === void 0) {
              return void 0;
            }
          }
          result[i] = c;
        }
        return result;
      };
      sizeOf.MACSTRING = function(str, encoding) {
        var b2 = encode.MACSTRING(str, encoding);
        if (b2 !== void 0) {
          return b2.length;
        } else {
          return 0;
        }
      };
      function isByteEncodable(value) {
        return value >= -128 && value <= 127;
      }
      function encodeVarDeltaRunAsZeroes(deltas, pos, result) {
        var runLength = 0;
        var numDeltas = deltas.length;
        while (pos < numDeltas && runLength < 64 && deltas[pos] === 0) {
          ++pos;
          ++runLength;
        }
        result.push(128 | runLength - 1);
        return pos;
      }
      function encodeVarDeltaRunAsBytes(deltas, offset, result) {
        var runLength = 0;
        var numDeltas = deltas.length;
        var pos = offset;
        while (pos < numDeltas && runLength < 64) {
          var value = deltas[pos];
          if (!isByteEncodable(value)) {
            break;
          }
          if (value === 0 && pos + 1 < numDeltas && deltas[pos + 1] === 0) {
            break;
          }
          ++pos;
          ++runLength;
        }
        result.push(runLength - 1);
        for (var i = offset; i < pos; ++i) {
          result.push(deltas[i] + 256 & 255);
        }
        return pos;
      }
      function encodeVarDeltaRunAsWords(deltas, offset, result) {
        var runLength = 0;
        var numDeltas = deltas.length;
        var pos = offset;
        while (pos < numDeltas && runLength < 64) {
          var value = deltas[pos];
          if (value === 0) {
            break;
          }
          if (isByteEncodable(value) && pos + 1 < numDeltas && isByteEncodable(deltas[pos + 1])) {
            break;
          }
          ++pos;
          ++runLength;
        }
        result.push(64 | runLength - 1);
        for (var i = offset; i < pos; ++i) {
          var val = deltas[i];
          result.push(val + 65536 >> 8 & 255, val + 256 & 255);
        }
        return pos;
      }
      encode.VARDELTAS = function(deltas) {
        var pos = 0;
        var result = [];
        while (pos < deltas.length) {
          var value = deltas[pos];
          if (value === 0) {
            pos = encodeVarDeltaRunAsZeroes(deltas, pos, result);
          } else if (value >= -128 && value <= 127) {
            pos = encodeVarDeltaRunAsBytes(deltas, pos, result);
          } else {
            pos = encodeVarDeltaRunAsWords(deltas, pos, result);
          }
        }
        return result;
      };
      encode.INDEX = function(l) {
        var offset = 1;
        var offsets = [offset];
        var data = [];
        for (var i = 0; i < l.length; i += 1) {
          var v = encode.OBJECT(l[i]);
          Array.prototype.push.apply(data, v);
          offset += v.length;
          offsets.push(offset);
        }
        if (data.length === 0) {
          return [0, 0];
        }
        var encodedOffsets = [];
        var offSize = 1 + Math.floor(Math.log(offset) / Math.log(2)) / 8 | 0;
        var offsetEncoder = [void 0, encode.BYTE, encode.USHORT, encode.UINT24, encode.ULONG][offSize];
        for (var i$1 = 0; i$1 < offsets.length; i$1 += 1) {
          var encodedOffset = offsetEncoder(offsets[i$1]);
          Array.prototype.push.apply(encodedOffsets, encodedOffset);
        }
        return Array.prototype.concat(
          encode.Card16(l.length),
          encode.OffSize(offSize),
          encodedOffsets,
          data
        );
      };
      sizeOf.INDEX = function(v) {
        return encode.INDEX(v).length;
      };
      encode.DICT = function(m) {
        var d = [];
        var keys = Object.keys(m);
        var length = keys.length;
        for (var i = 0; i < length; i += 1) {
          var k = parseInt(keys[i], 0);
          var v = m[k];
          d = d.concat(encode.OPERAND(v.value, v.type));
          d = d.concat(encode.OPERATOR(k));
        }
        return d;
      };
      sizeOf.DICT = function(m) {
        return encode.DICT(m).length;
      };
      encode.OPERATOR = function(v) {
        if (v < 1200) {
          return [v];
        } else {
          return [12, v - 1200];
        }
      };
      encode.OPERAND = function(v, type) {
        var d = [];
        if (Array.isArray(type)) {
          for (var i = 0; i < type.length; i += 1) {
            check.argument(v.length === type.length, "Not enough arguments given for type" + type);
            d = d.concat(encode.OPERAND(v[i], type[i]));
          }
        } else {
          if (type === "SID") {
            d = d.concat(encode.NUMBER(v));
          } else if (type === "offset") {
            d = d.concat(encode.NUMBER32(v));
          } else if (type === "number") {
            d = d.concat(encode.NUMBER(v));
          } else if (type === "real") {
            d = d.concat(encode.REAL(v));
          } else {
            throw new Error("Unknown operand type " + type);
          }
        }
        return d;
      };
      encode.OP = encode.BYTE;
      sizeOf.OP = sizeOf.BYTE;
      var wmm = typeof WeakMap === "function" && /* @__PURE__ */ new WeakMap();
      encode.CHARSTRING = function(ops) {
        if (wmm) {
          var cachedValue = wmm.get(ops);
          if (cachedValue !== void 0) {
            return cachedValue;
          }
        }
        var d = [];
        var length = ops.length;
        for (var i = 0; i < length; i += 1) {
          var op = ops[i];
          d = d.concat(encode[op.type](op.value));
        }
        if (wmm) {
          wmm.set(ops, d);
        }
        return d;
      };
      sizeOf.CHARSTRING = function(ops) {
        return encode.CHARSTRING(ops).length;
      };
      encode.OBJECT = function(v) {
        var encodingFunction = encode[v.type];
        check.argument(encodingFunction !== void 0, "No encoding function for type " + v.type);
        return encodingFunction(v.value);
      };
      sizeOf.OBJECT = function(v) {
        var sizeOfFunction = sizeOf[v.type];
        check.argument(sizeOfFunction !== void 0, "No sizeOf function for type " + v.type);
        return sizeOfFunction(v.value);
      };
      encode.TABLE = function(table3) {
        var d = [];
        var length = table3.fields.length;
        var subtables = [];
        var subtableOffsets = [];
        for (var i = 0; i < length; i += 1) {
          var field = table3.fields[i];
          var encodingFunction = encode[field.type];
          check.argument(encodingFunction !== void 0, "No encoding function for field type " + field.type + " (" + field.name + ")");
          var value = table3[field.name];
          if (value === void 0) {
            value = field.value;
          }
          var bytes = encodingFunction(value);
          if (field.type === "TABLE") {
            subtableOffsets.push(d.length);
            d = d.concat([0, 0]);
            subtables.push(bytes);
          } else {
            d = d.concat(bytes);
          }
        }
        for (var i$1 = 0; i$1 < subtables.length; i$1 += 1) {
          var o = subtableOffsets[i$1];
          var offset = d.length;
          check.argument(offset < 65536, "Table " + table3.tableName + " too big.");
          d[o] = offset >> 8;
          d[o + 1] = offset & 255;
          d = d.concat(subtables[i$1]);
        }
        return d;
      };
      sizeOf.TABLE = function(table3) {
        var numBytes = 0;
        var length = table3.fields.length;
        for (var i = 0; i < length; i += 1) {
          var field = table3.fields[i];
          var sizeOfFunction = sizeOf[field.type];
          check.argument(sizeOfFunction !== void 0, "No sizeOf function for field type " + field.type + " (" + field.name + ")");
          var value = table3[field.name];
          if (value === void 0) {
            value = field.value;
          }
          numBytes += sizeOfFunction(value);
          if (field.type === "TABLE") {
            numBytes += 2;
          }
        }
        return numBytes;
      };
      encode.RECORD = encode.TABLE;
      sizeOf.RECORD = sizeOf.TABLE;
      encode.LITERAL = function(v) {
        return v;
      };
      sizeOf.LITERAL = function(v) {
        return v.length;
      };
      function Table(tableName, fields, options) {
        if (fields.length && (fields[0].name !== "coverageFormat" || fields[0].value === 1)) {
          for (var i = 0; i < fields.length; i += 1) {
            var field = fields[i];
            this[field.name] = field.value;
          }
        }
        this.tableName = tableName;
        this.fields = fields;
        if (options) {
          var optionKeys = Object.keys(options);
          for (var i$1 = 0; i$1 < optionKeys.length; i$1 += 1) {
            var k = optionKeys[i$1];
            var v = options[k];
            if (this[k] !== void 0) {
              this[k] = v;
            }
          }
        }
      }
      Table.prototype.encode = function() {
        return encode.TABLE(this);
      };
      Table.prototype.sizeOf = function() {
        return sizeOf.TABLE(this);
      };
      function ushortList(itemName, list, count) {
        if (count === void 0) {
          count = list.length;
        }
        var fields = new Array(list.length + 1);
        fields[0] = { name: itemName + "Count", type: "USHORT", value: count };
        for (var i = 0; i < list.length; i++) {
          fields[i + 1] = { name: itemName + i, type: "USHORT", value: list[i] };
        }
        return fields;
      }
      function tableList(itemName, records, itemCallback) {
        var count = records.length;
        var fields = new Array(count + 1);
        fields[0] = { name: itemName + "Count", type: "USHORT", value: count };
        for (var i = 0; i < count; i++) {
          fields[i + 1] = { name: itemName + i, type: "TABLE", value: itemCallback(records[i], i) };
        }
        return fields;
      }
      function recordList(itemName, records, itemCallback) {
        var count = records.length;
        var fields = [];
        fields[0] = { name: itemName + "Count", type: "USHORT", value: count };
        for (var i = 0; i < count; i++) {
          fields = fields.concat(itemCallback(records[i], i));
        }
        return fields;
      }
      function Coverage(coverageTable) {
        if (coverageTable.format === 1) {
          Table.call(
            this,
            "coverageTable",
            [{ name: "coverageFormat", type: "USHORT", value: 1 }].concat(ushortList("glyph", coverageTable.glyphs))
          );
        } else if (coverageTable.format === 2) {
          Table.call(
            this,
            "coverageTable",
            [{ name: "coverageFormat", type: "USHORT", value: 2 }].concat(recordList("rangeRecord", coverageTable.ranges, function(RangeRecord) {
              return [
                { name: "startGlyphID", type: "USHORT", value: RangeRecord.start },
                { name: "endGlyphID", type: "USHORT", value: RangeRecord.end },
                { name: "startCoverageIndex", type: "USHORT", value: RangeRecord.index }
              ];
            }))
          );
        } else {
          check.assert(false, "Coverage format must be 1 or 2.");
        }
      }
      Coverage.prototype = Object.create(Table.prototype);
      Coverage.prototype.constructor = Coverage;
      function ScriptList(scriptListTable) {
        Table.call(
          this,
          "scriptListTable",
          recordList("scriptRecord", scriptListTable, function(scriptRecord, i) {
            var script = scriptRecord.script;
            var defaultLangSys = script.defaultLangSys;
            check.assert(!!defaultLangSys, "Unable to write GSUB: script " + scriptRecord.tag + " has no default language system.");
            return [
              { name: "scriptTag" + i, type: "TAG", value: scriptRecord.tag },
              { name: "script" + i, type: "TABLE", value: new Table("scriptTable", [
                { name: "defaultLangSys", type: "TABLE", value: new Table("defaultLangSys", [
                  { name: "lookupOrder", type: "USHORT", value: 0 },
                  { name: "reqFeatureIndex", type: "USHORT", value: defaultLangSys.reqFeatureIndex }
                ].concat(ushortList("featureIndex", defaultLangSys.featureIndexes))) }
              ].concat(recordList("langSys", script.langSysRecords, function(langSysRecord, i2) {
                var langSys = langSysRecord.langSys;
                return [
                  { name: "langSysTag" + i2, type: "TAG", value: langSysRecord.tag },
                  { name: "langSys" + i2, type: "TABLE", value: new Table("langSys", [
                    { name: "lookupOrder", type: "USHORT", value: 0 },
                    { name: "reqFeatureIndex", type: "USHORT", value: langSys.reqFeatureIndex }
                  ].concat(ushortList("featureIndex", langSys.featureIndexes))) }
                ];
              }))) }
            ];
          })
        );
      }
      ScriptList.prototype = Object.create(Table.prototype);
      ScriptList.prototype.constructor = ScriptList;
      function FeatureList(featureListTable) {
        Table.call(
          this,
          "featureListTable",
          recordList("featureRecord", featureListTable, function(featureRecord, i) {
            var feature = featureRecord.feature;
            return [
              { name: "featureTag" + i, type: "TAG", value: featureRecord.tag },
              { name: "feature" + i, type: "TABLE", value: new Table("featureTable", [
                { name: "featureParams", type: "USHORT", value: feature.featureParams }
              ].concat(ushortList("lookupListIndex", feature.lookupListIndexes))) }
            ];
          })
        );
      }
      FeatureList.prototype = Object.create(Table.prototype);
      FeatureList.prototype.constructor = FeatureList;
      function LookupList(lookupListTable, subtableMakers2) {
        Table.call(this, "lookupListTable", tableList("lookup", lookupListTable, function(lookupTable) {
          var subtableCallback = subtableMakers2[lookupTable.lookupType];
          check.assert(!!subtableCallback, "Unable to write GSUB lookup type " + lookupTable.lookupType + " tables.");
          return new Table("lookupTable", [
            { name: "lookupType", type: "USHORT", value: lookupTable.lookupType },
            { name: "lookupFlag", type: "USHORT", value: lookupTable.lookupFlag }
          ].concat(tableList("subtable", lookupTable.subtables, subtableCallback)));
        }));
      }
      LookupList.prototype = Object.create(Table.prototype);
      LookupList.prototype.constructor = LookupList;
      var table2 = {
        Table,
        Record: Table,
        Coverage,
        ScriptList,
        FeatureList,
        LookupList,
        ushortList,
        tableList,
        recordList
      };
      function getByte(dataView, offset) {
        return dataView.getUint8(offset);
      }
      function getUShort(dataView, offset) {
        return dataView.getUint16(offset, false);
      }
      function getShort(dataView, offset) {
        return dataView.getInt16(offset, false);
      }
      function getULong(dataView, offset) {
        return dataView.getUint32(offset, false);
      }
      function getFixed(dataView, offset) {
        var decimal = dataView.getInt16(offset, false);
        var fraction = dataView.getUint16(offset + 2, false);
        return decimal + fraction / 65535;
      }
      function getTag(dataView, offset) {
        var tag = "";
        for (var i = offset; i < offset + 4; i += 1) {
          tag += String.fromCharCode(dataView.getInt8(i));
        }
        return tag;
      }
      function getOffset(dataView, offset, offSize) {
        var v = 0;
        for (var i = 0; i < offSize; i += 1) {
          v <<= 8;
          v += dataView.getUint8(offset + i);
        }
        return v;
      }
      function getBytes(dataView, startOffset, endOffset) {
        var bytes = [];
        for (var i = startOffset; i < endOffset; i += 1) {
          bytes.push(dataView.getUint8(i));
        }
        return bytes;
      }
      function bytesToString(bytes) {
        var s = "";
        for (var i = 0; i < bytes.length; i += 1) {
          s += String.fromCharCode(bytes[i]);
        }
        return s;
      }
      var typeOffsets = {
        byte: 1,
        uShort: 2,
        short: 2,
        uLong: 4,
        fixed: 4,
        longDateTime: 8,
        tag: 4
      };
      function Parser(data, offset) {
        this.data = data;
        this.offset = offset;
        this.relativeOffset = 0;
      }
      Parser.prototype.parseByte = function() {
        var v = this.data.getUint8(this.offset + this.relativeOffset);
        this.relativeOffset += 1;
        return v;
      };
      Parser.prototype.parseChar = function() {
        var v = this.data.getInt8(this.offset + this.relativeOffset);
        this.relativeOffset += 1;
        return v;
      };
      Parser.prototype.parseCard8 = Parser.prototype.parseByte;
      Parser.prototype.parseUShort = function() {
        var v = this.data.getUint16(this.offset + this.relativeOffset);
        this.relativeOffset += 2;
        return v;
      };
      Parser.prototype.parseCard16 = Parser.prototype.parseUShort;
      Parser.prototype.parseSID = Parser.prototype.parseUShort;
      Parser.prototype.parseOffset16 = Parser.prototype.parseUShort;
      Parser.prototype.parseShort = function() {
        var v = this.data.getInt16(this.offset + this.relativeOffset);
        this.relativeOffset += 2;
        return v;
      };
      Parser.prototype.parseF2Dot14 = function() {
        var v = this.data.getInt16(this.offset + this.relativeOffset) / 16384;
        this.relativeOffset += 2;
        return v;
      };
      Parser.prototype.parseULong = function() {
        var v = getULong(this.data, this.offset + this.relativeOffset);
        this.relativeOffset += 4;
        return v;
      };
      Parser.prototype.parseOffset32 = Parser.prototype.parseULong;
      Parser.prototype.parseFixed = function() {
        var v = getFixed(this.data, this.offset + this.relativeOffset);
        this.relativeOffset += 4;
        return v;
      };
      Parser.prototype.parseString = function(length) {
        var dataView = this.data;
        var offset = this.offset + this.relativeOffset;
        var string = "";
        this.relativeOffset += length;
        for (var i = 0; i < length; i++) {
          string += String.fromCharCode(dataView.getUint8(offset + i));
        }
        return string;
      };
      Parser.prototype.parseTag = function() {
        return this.parseString(4);
      };
      Parser.prototype.parseLongDateTime = function() {
        var v = getULong(this.data, this.offset + this.relativeOffset + 4);
        v -= 2082844800;
        this.relativeOffset += 8;
        return v;
      };
      Parser.prototype.parseVersion = function(minorBase) {
        var major = getUShort(this.data, this.offset + this.relativeOffset);
        var minor = getUShort(this.data, this.offset + this.relativeOffset + 2);
        this.relativeOffset += 4;
        if (minorBase === void 0) {
          minorBase = 4096;
        }
        return major + minor / minorBase / 10;
      };
      Parser.prototype.skip = function(type, amount) {
        if (amount === void 0) {
          amount = 1;
        }
        this.relativeOffset += typeOffsets[type] * amount;
      };
      Parser.prototype.parseULongList = function(count) {
        if (count === void 0) {
          count = this.parseULong();
        }
        var offsets = new Array(count);
        var dataView = this.data;
        var offset = this.offset + this.relativeOffset;
        for (var i = 0; i < count; i++) {
          offsets[i] = dataView.getUint32(offset);
          offset += 4;
        }
        this.relativeOffset += count * 4;
        return offsets;
      };
      Parser.prototype.parseOffset16List = Parser.prototype.parseUShortList = function(count) {
        if (count === void 0) {
          count = this.parseUShort();
        }
        var offsets = new Array(count);
        var dataView = this.data;
        var offset = this.offset + this.relativeOffset;
        for (var i = 0; i < count; i++) {
          offsets[i] = dataView.getUint16(offset);
          offset += 2;
        }
        this.relativeOffset += count * 2;
        return offsets;
      };
      Parser.prototype.parseShortList = function(count) {
        var list = new Array(count);
        var dataView = this.data;
        var offset = this.offset + this.relativeOffset;
        for (var i = 0; i < count; i++) {
          list[i] = dataView.getInt16(offset);
          offset += 2;
        }
        this.relativeOffset += count * 2;
        return list;
      };
      Parser.prototype.parseByteList = function(count) {
        var list = new Array(count);
        var dataView = this.data;
        var offset = this.offset + this.relativeOffset;
        for (var i = 0; i < count; i++) {
          list[i] = dataView.getUint8(offset++);
        }
        this.relativeOffset += count;
        return list;
      };
      Parser.prototype.parseList = function(count, itemCallback) {
        if (!itemCallback) {
          itemCallback = count;
          count = this.parseUShort();
        }
        var list = new Array(count);
        for (var i = 0; i < count; i++) {
          list[i] = itemCallback.call(this);
        }
        return list;
      };
      Parser.prototype.parseList32 = function(count, itemCallback) {
        if (!itemCallback) {
          itemCallback = count;
          count = this.parseULong();
        }
        var list = new Array(count);
        for (var i = 0; i < count; i++) {
          list[i] = itemCallback.call(this);
        }
        return list;
      };
      Parser.prototype.parseRecordList = function(count, recordDescription) {
        if (!recordDescription) {
          recordDescription = count;
          count = this.parseUShort();
        }
        var records = new Array(count);
        var fields = Object.keys(recordDescription);
        for (var i = 0; i < count; i++) {
          var rec = {};
          for (var j = 0; j < fields.length; j++) {
            var fieldName = fields[j];
            var fieldType = recordDescription[fieldName];
            rec[fieldName] = fieldType.call(this);
          }
          records[i] = rec;
        }
        return records;
      };
      Parser.prototype.parseRecordList32 = function(count, recordDescription) {
        if (!recordDescription) {
          recordDescription = count;
          count = this.parseULong();
        }
        var records = new Array(count);
        var fields = Object.keys(recordDescription);
        for (var i = 0; i < count; i++) {
          var rec = {};
          for (var j = 0; j < fields.length; j++) {
            var fieldName = fields[j];
            var fieldType = recordDescription[fieldName];
            rec[fieldName] = fieldType.call(this);
          }
          records[i] = rec;
        }
        return records;
      };
      Parser.prototype.parseStruct = function(description) {
        if (typeof description === "function") {
          return description.call(this);
        } else {
          var fields = Object.keys(description);
          var struct = {};
          for (var j = 0; j < fields.length; j++) {
            var fieldName = fields[j];
            var fieldType = description[fieldName];
            struct[fieldName] = fieldType.call(this);
          }
          return struct;
        }
      };
      Parser.prototype.parseValueRecord = function(valueFormat) {
        if (valueFormat === void 0) {
          valueFormat = this.parseUShort();
        }
        if (valueFormat === 0) {
          return;
        }
        var valueRecord = {};
        if (valueFormat & 1) {
          valueRecord.xPlacement = this.parseShort();
        }
        if (valueFormat & 2) {
          valueRecord.yPlacement = this.parseShort();
        }
        if (valueFormat & 4) {
          valueRecord.xAdvance = this.parseShort();
        }
        if (valueFormat & 8) {
          valueRecord.yAdvance = this.parseShort();
        }
        if (valueFormat & 16) {
          valueRecord.xPlaDevice = void 0;
          this.parseShort();
        }
        if (valueFormat & 32) {
          valueRecord.yPlaDevice = void 0;
          this.parseShort();
        }
        if (valueFormat & 64) {
          valueRecord.xAdvDevice = void 0;
          this.parseShort();
        }
        if (valueFormat & 128) {
          valueRecord.yAdvDevice = void 0;
          this.parseShort();
        }
        return valueRecord;
      };
      Parser.prototype.parseValueRecordList = function() {
        var valueFormat = this.parseUShort();
        var valueCount = this.parseUShort();
        var values2 = new Array(valueCount);
        for (var i = 0; i < valueCount; i++) {
          values2[i] = this.parseValueRecord(valueFormat);
        }
        return values2;
      };
      Parser.prototype.parsePointer = function(description) {
        var structOffset = this.parseOffset16();
        if (structOffset > 0) {
          return new Parser(this.data, this.offset + structOffset).parseStruct(description);
        }
        return void 0;
      };
      Parser.prototype.parsePointer32 = function(description) {
        var structOffset = this.parseOffset32();
        if (structOffset > 0) {
          return new Parser(this.data, this.offset + structOffset).parseStruct(description);
        }
        return void 0;
      };
      Parser.prototype.parseListOfLists = function(itemCallback) {
        var offsets = this.parseOffset16List();
        var count = offsets.length;
        var relativeOffset = this.relativeOffset;
        var list = new Array(count);
        for (var i = 0; i < count; i++) {
          var start = offsets[i];
          if (start === 0) {
            list[i] = void 0;
            continue;
          }
          this.relativeOffset = start;
          if (itemCallback) {
            var subOffsets = this.parseOffset16List();
            var subList = new Array(subOffsets.length);
            for (var j = 0; j < subOffsets.length; j++) {
              this.relativeOffset = start + subOffsets[j];
              subList[j] = itemCallback.call(this);
            }
            list[i] = subList;
          } else {
            list[i] = this.parseUShortList();
          }
        }
        this.relativeOffset = relativeOffset;
        return list;
      };
      Parser.prototype.parseCoverage = function() {
        var startOffset = this.offset + this.relativeOffset;
        var format = this.parseUShort();
        var count = this.parseUShort();
        if (format === 1) {
          return {
            format: 1,
            glyphs: this.parseUShortList(count)
          };
        } else if (format === 2) {
          var ranges = new Array(count);
          for (var i = 0; i < count; i++) {
            ranges[i] = {
              start: this.parseUShort(),
              end: this.parseUShort(),
              index: this.parseUShort()
            };
          }
          return {
            format: 2,
            ranges
          };
        }
        throw new Error("0x" + startOffset.toString(16) + ": Coverage format must be 1 or 2.");
      };
      Parser.prototype.parseClassDef = function() {
        var startOffset = this.offset + this.relativeOffset;
        var format = this.parseUShort();
        if (format === 1) {
          return {
            format: 1,
            startGlyph: this.parseUShort(),
            classes: this.parseUShortList()
          };
        } else if (format === 2) {
          return {
            format: 2,
            ranges: this.parseRecordList({
              start: Parser.uShort,
              end: Parser.uShort,
              classId: Parser.uShort
            })
          };
        }
        throw new Error("0x" + startOffset.toString(16) + ": ClassDef format must be 1 or 2.");
      };
      Parser.list = function(count, itemCallback) {
        return function() {
          return this.parseList(count, itemCallback);
        };
      };
      Parser.list32 = function(count, itemCallback) {
        return function() {
          return this.parseList32(count, itemCallback);
        };
      };
      Parser.recordList = function(count, recordDescription) {
        return function() {
          return this.parseRecordList(count, recordDescription);
        };
      };
      Parser.recordList32 = function(count, recordDescription) {
        return function() {
          return this.parseRecordList32(count, recordDescription);
        };
      };
      Parser.pointer = function(description) {
        return function() {
          return this.parsePointer(description);
        };
      };
      Parser.pointer32 = function(description) {
        return function() {
          return this.parsePointer32(description);
        };
      };
      Parser.tag = Parser.prototype.parseTag;
      Parser.byte = Parser.prototype.parseByte;
      Parser.uShort = Parser.offset16 = Parser.prototype.parseUShort;
      Parser.uShortList = Parser.prototype.parseUShortList;
      Parser.uLong = Parser.offset32 = Parser.prototype.parseULong;
      Parser.uLongList = Parser.prototype.parseULongList;
      Parser.struct = Parser.prototype.parseStruct;
      Parser.coverage = Parser.prototype.parseCoverage;
      Parser.classDef = Parser.prototype.parseClassDef;
      var langSysTable = {
        reserved: Parser.uShort,
        reqFeatureIndex: Parser.uShort,
        featureIndexes: Parser.uShortList
      };
      Parser.prototype.parseScriptList = function() {
        return this.parsePointer(Parser.recordList({
          tag: Parser.tag,
          script: Parser.pointer({
            defaultLangSys: Parser.pointer(langSysTable),
            langSysRecords: Parser.recordList({
              tag: Parser.tag,
              langSys: Parser.pointer(langSysTable)
            })
          })
        })) || [];
      };
      Parser.prototype.parseFeatureList = function() {
        return this.parsePointer(Parser.recordList({
          tag: Parser.tag,
          feature: Parser.pointer({
            featureParams: Parser.offset16,
            lookupListIndexes: Parser.uShortList
          })
        })) || [];
      };
      Parser.prototype.parseLookupList = function(lookupTableParsers) {
        return this.parsePointer(Parser.list(Parser.pointer(function() {
          var lookupType = this.parseUShort();
          check.argument(1 <= lookupType && lookupType <= 9, "GPOS/GSUB lookup type " + lookupType + " unknown.");
          var lookupFlag = this.parseUShort();
          var useMarkFilteringSet = lookupFlag & 16;
          return {
            lookupType,
            lookupFlag,
            subtables: this.parseList(Parser.pointer(lookupTableParsers[lookupType])),
            markFilteringSet: useMarkFilteringSet ? this.parseUShort() : void 0
          };
        }))) || [];
      };
      Parser.prototype.parseFeatureVariationsList = function() {
        return this.parsePointer32(function() {
          var majorVersion = this.parseUShort();
          var minorVersion = this.parseUShort();
          check.argument(majorVersion === 1 && minorVersion < 1, "GPOS/GSUB feature variations table unknown.");
          var featureVariations = this.parseRecordList32({
            conditionSetOffset: Parser.offset32,
            featureTableSubstitutionOffset: Parser.offset32
          });
          return featureVariations;
        }) || [];
      };
      var parse2 = {
        getByte,
        getCard8: getByte,
        getUShort,
        getCard16: getUShort,
        getShort,
        getULong,
        getFixed,
        getTag,
        getOffset,
        getBytes,
        bytesToString,
        Parser
      };
      function parseCmapTableFormat12(cmap2, p) {
        p.parseUShort();
        cmap2.length = p.parseULong();
        cmap2.language = p.parseULong();
        var groupCount;
        cmap2.groupCount = groupCount = p.parseULong();
        cmap2.glyphIndexMap = {};
        for (var i = 0; i < groupCount; i += 1) {
          var startCharCode = p.parseULong();
          var endCharCode = p.parseULong();
          var startGlyphId = p.parseULong();
          for (var c = startCharCode; c <= endCharCode; c += 1) {
            cmap2.glyphIndexMap[c] = startGlyphId;
            startGlyphId++;
          }
        }
      }
      function parseCmapTableFormat4(cmap2, p, data, start, offset) {
        cmap2.length = p.parseUShort();
        cmap2.language = p.parseUShort();
        var segCount;
        cmap2.segCount = segCount = p.parseUShort() >> 1;
        p.skip("uShort", 3);
        cmap2.glyphIndexMap = {};
        var endCountParser = new parse2.Parser(data, start + offset + 14);
        var startCountParser = new parse2.Parser(data, start + offset + 16 + segCount * 2);
        var idDeltaParser = new parse2.Parser(data, start + offset + 16 + segCount * 4);
        var idRangeOffsetParser = new parse2.Parser(data, start + offset + 16 + segCount * 6);
        var glyphIndexOffset = start + offset + 16 + segCount * 8;
        for (var i = 0; i < segCount - 1; i += 1) {
          var glyphIndex = void 0;
          var endCount = endCountParser.parseUShort();
          var startCount = startCountParser.parseUShort();
          var idDelta = idDeltaParser.parseShort();
          var idRangeOffset = idRangeOffsetParser.parseUShort();
          for (var c = startCount; c <= endCount; c += 1) {
            if (idRangeOffset !== 0) {
              glyphIndexOffset = idRangeOffsetParser.offset + idRangeOffsetParser.relativeOffset - 2;
              glyphIndexOffset += idRangeOffset;
              glyphIndexOffset += (c - startCount) * 2;
              glyphIndex = parse2.getUShort(data, glyphIndexOffset);
              if (glyphIndex !== 0) {
                glyphIndex = glyphIndex + idDelta & 65535;
              }
            } else {
              glyphIndex = c + idDelta & 65535;
            }
            cmap2.glyphIndexMap[c] = glyphIndex;
          }
        }
      }
      function parseCmapTable(data, start) {
        var cmap2 = {};
        cmap2.version = parse2.getUShort(data, start);
        check.argument(cmap2.version === 0, "cmap table version should be 0.");
        cmap2.numTables = parse2.getUShort(data, start + 2);
        var offset = -1;
        for (var i = cmap2.numTables - 1; i >= 0; i -= 1) {
          var platformId = parse2.getUShort(data, start + 4 + i * 8);
          var encodingId = parse2.getUShort(data, start + 4 + i * 8 + 2);
          if (platformId === 3 && (encodingId === 0 || encodingId === 1 || encodingId === 10) || platformId === 0 && (encodingId === 0 || encodingId === 1 || encodingId === 2 || encodingId === 3 || encodingId === 4)) {
            offset = parse2.getULong(data, start + 4 + i * 8 + 4);
            break;
          }
        }
        if (offset === -1) {
          throw new Error("No valid cmap sub-tables found.");
        }
        var p = new parse2.Parser(data, start + offset);
        cmap2.format = p.parseUShort();
        if (cmap2.format === 12) {
          parseCmapTableFormat12(cmap2, p);
        } else if (cmap2.format === 4) {
          parseCmapTableFormat4(cmap2, p, data, start, offset);
        } else {
          throw new Error("Only format 4 and 12 cmap tables are supported (found format " + cmap2.format + ").");
        }
        return cmap2;
      }
      function addSegment(t, code, glyphIndex) {
        t.segments.push({
          end: code,
          start: code,
          delta: -(code - glyphIndex),
          offset: 0,
          glyphIndex
        });
      }
      function addTerminatorSegment(t) {
        t.segments.push({
          end: 65535,
          start: 65535,
          delta: 1,
          offset: 0
        });
      }
      function makeCmapTable(glyphs) {
        var isPlan0Only = true;
        var i;
        for (i = glyphs.length - 1; i > 0; i -= 1) {
          var g = glyphs.get(i);
          if (g.unicode > 65535) {
            console.log("Adding CMAP format 12 (needed!)");
            isPlan0Only = false;
            break;
          }
        }
        var cmapTable = [
          { name: "version", type: "USHORT", value: 0 },
          { name: "numTables", type: "USHORT", value: isPlan0Only ? 1 : 2 },
          // CMAP 4 header
          { name: "platformID", type: "USHORT", value: 3 },
          { name: "encodingID", type: "USHORT", value: 1 },
          { name: "offset", type: "ULONG", value: isPlan0Only ? 12 : 12 + 8 }
        ];
        if (!isPlan0Only) {
          cmapTable = cmapTable.concat([
            // CMAP 12 header
            { name: "cmap12PlatformID", type: "USHORT", value: 3 },
            // We encode only for PlatformID = 3 (Windows) because it is supported everywhere
            { name: "cmap12EncodingID", type: "USHORT", value: 10 },
            { name: "cmap12Offset", type: "ULONG", value: 0 }
          ]);
        }
        cmapTable = cmapTable.concat([
          // CMAP 4 Subtable
          { name: "format", type: "USHORT", value: 4 },
          { name: "cmap4Length", type: "USHORT", value: 0 },
          { name: "language", type: "USHORT", value: 0 },
          { name: "segCountX2", type: "USHORT", value: 0 },
          { name: "searchRange", type: "USHORT", value: 0 },
          { name: "entrySelector", type: "USHORT", value: 0 },
          { name: "rangeShift", type: "USHORT", value: 0 }
        ]);
        var t = new table2.Table("cmap", cmapTable);
        t.segments = [];
        for (i = 0; i < glyphs.length; i += 1) {
          var glyph = glyphs.get(i);
          for (var j = 0; j < glyph.unicodes.length; j += 1) {
            addSegment(t, glyph.unicodes[j], i);
          }
          t.segments = t.segments.sort(function(a, b2) {
            return a.start - b2.start;
          });
        }
        addTerminatorSegment(t);
        var segCount = t.segments.length;
        var segCountToRemove = 0;
        var endCounts = [];
        var startCounts = [];
        var idDeltas = [];
        var idRangeOffsets = [];
        var glyphIds = [];
        var cmap12Groups = [];
        for (i = 0; i < segCount; i += 1) {
          var segment = t.segments[i];
          if (segment.end <= 65535 && segment.start <= 65535) {
            endCounts = endCounts.concat({ name: "end_" + i, type: "USHORT", value: segment.end });
            startCounts = startCounts.concat({ name: "start_" + i, type: "USHORT", value: segment.start });
            idDeltas = idDeltas.concat({ name: "idDelta_" + i, type: "SHORT", value: segment.delta });
            idRangeOffsets = idRangeOffsets.concat({ name: "idRangeOffset_" + i, type: "USHORT", value: segment.offset });
            if (segment.glyphId !== void 0) {
              glyphIds = glyphIds.concat({ name: "glyph_" + i, type: "USHORT", value: segment.glyphId });
            }
          } else {
            segCountToRemove += 1;
          }
          if (!isPlan0Only && segment.glyphIndex !== void 0) {
            cmap12Groups = cmap12Groups.concat({ name: "cmap12Start_" + i, type: "ULONG", value: segment.start });
            cmap12Groups = cmap12Groups.concat({ name: "cmap12End_" + i, type: "ULONG", value: segment.end });
            cmap12Groups = cmap12Groups.concat({ name: "cmap12Glyph_" + i, type: "ULONG", value: segment.glyphIndex });
          }
        }
        t.segCountX2 = (segCount - segCountToRemove) * 2;
        t.searchRange = Math.pow(2, Math.floor(Math.log(segCount - segCountToRemove) / Math.log(2))) * 2;
        t.entrySelector = Math.log(t.searchRange / 2) / Math.log(2);
        t.rangeShift = t.segCountX2 - t.searchRange;
        t.fields = t.fields.concat(endCounts);
        t.fields.push({ name: "reservedPad", type: "USHORT", value: 0 });
        t.fields = t.fields.concat(startCounts);
        t.fields = t.fields.concat(idDeltas);
        t.fields = t.fields.concat(idRangeOffsets);
        t.fields = t.fields.concat(glyphIds);
        t.cmap4Length = 14 + // Subtable header
        endCounts.length * 2 + 2 + // reservedPad
        startCounts.length * 2 + idDeltas.length * 2 + idRangeOffsets.length * 2 + glyphIds.length * 2;
        if (!isPlan0Only) {
          var cmap12Length = 16 + // Subtable header
          cmap12Groups.length * 4;
          t.cmap12Offset = 12 + 2 * 2 + 4 + t.cmap4Length;
          t.fields = t.fields.concat([
            { name: "cmap12Format", type: "USHORT", value: 12 },
            { name: "cmap12Reserved", type: "USHORT", value: 0 },
            { name: "cmap12Length", type: "ULONG", value: cmap12Length },
            { name: "cmap12Language", type: "ULONG", value: 0 },
            { name: "cmap12nGroups", type: "ULONG", value: cmap12Groups.length / 3 }
          ]);
          t.fields = t.fields.concat(cmap12Groups);
        }
        return t;
      }
      var cmap = { parse: parseCmapTable, make: makeCmapTable };
      var cffStandardStrings = [
        ".notdef",
        "space",
        "exclam",
        "quotedbl",
        "numbersign",
        "dollar",
        "percent",
        "ampersand",
        "quoteright",
        "parenleft",
        "parenright",
        "asterisk",
        "plus",
        "comma",
        "hyphen",
        "period",
        "slash",
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "colon",
        "semicolon",
        "less",
        "equal",
        "greater",
        "question",
        "at",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
        "Z",
        "bracketleft",
        "backslash",
        "bracketright",
        "asciicircum",
        "underscore",
        "quoteleft",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "braceleft",
        "bar",
        "braceright",
        "asciitilde",
        "exclamdown",
        "cent",
        "sterling",
        "fraction",
        "yen",
        "florin",
        "section",
        "currency",
        "quotesingle",
        "quotedblleft",
        "guillemotleft",
        "guilsinglleft",
        "guilsinglright",
        "fi",
        "fl",
        "endash",
        "dagger",
        "daggerdbl",
        "periodcentered",
        "paragraph",
        "bullet",
        "quotesinglbase",
        "quotedblbase",
        "quotedblright",
        "guillemotright",
        "ellipsis",
        "perthousand",
        "questiondown",
        "grave",
        "acute",
        "circumflex",
        "tilde",
        "macron",
        "breve",
        "dotaccent",
        "dieresis",
        "ring",
        "cedilla",
        "hungarumlaut",
        "ogonek",
        "caron",
        "emdash",
        "AE",
        "ordfeminine",
        "Lslash",
        "Oslash",
        "OE",
        "ordmasculine",
        "ae",
        "dotlessi",
        "lslash",
        "oslash",
        "oe",
        "germandbls",
        "onesuperior",
        "logicalnot",
        "mu",
        "trademark",
        "Eth",
        "onehalf",
        "plusminus",
        "Thorn",
        "onequarter",
        "divide",
        "brokenbar",
        "degree",
        "thorn",
        "threequarters",
        "twosuperior",
        "registered",
        "minus",
        "eth",
        "multiply",
        "threesuperior",
        "copyright",
        "Aacute",
        "Acircumflex",
        "Adieresis",
        "Agrave",
        "Aring",
        "Atilde",
        "Ccedilla",
        "Eacute",
        "Ecircumflex",
        "Edieresis",
        "Egrave",
        "Iacute",
        "Icircumflex",
        "Idieresis",
        "Igrave",
        "Ntilde",
        "Oacute",
        "Ocircumflex",
        "Odieresis",
        "Ograve",
        "Otilde",
        "Scaron",
        "Uacute",
        "Ucircumflex",
        "Udieresis",
        "Ugrave",
        "Yacute",
        "Ydieresis",
        "Zcaron",
        "aacute",
        "acircumflex",
        "adieresis",
        "agrave",
        "aring",
        "atilde",
        "ccedilla",
        "eacute",
        "ecircumflex",
        "edieresis",
        "egrave",
        "iacute",
        "icircumflex",
        "idieresis",
        "igrave",
        "ntilde",
        "oacute",
        "ocircumflex",
        "odieresis",
        "ograve",
        "otilde",
        "scaron",
        "uacute",
        "ucircumflex",
        "udieresis",
        "ugrave",
        "yacute",
        "ydieresis",
        "zcaron",
        "exclamsmall",
        "Hungarumlautsmall",
        "dollaroldstyle",
        "dollarsuperior",
        "ampersandsmall",
        "Acutesmall",
        "parenleftsuperior",
        "parenrightsuperior",
        "266 ff",
        "onedotenleader",
        "zerooldstyle",
        "oneoldstyle",
        "twooldstyle",
        "threeoldstyle",
        "fouroldstyle",
        "fiveoldstyle",
        "sixoldstyle",
        "sevenoldstyle",
        "eightoldstyle",
        "nineoldstyle",
        "commasuperior",
        "threequartersemdash",
        "periodsuperior",
        "questionsmall",
        "asuperior",
        "bsuperior",
        "centsuperior",
        "dsuperior",
        "esuperior",
        "isuperior",
        "lsuperior",
        "msuperior",
        "nsuperior",
        "osuperior",
        "rsuperior",
        "ssuperior",
        "tsuperior",
        "ff",
        "ffi",
        "ffl",
        "parenleftinferior",
        "parenrightinferior",
        "Circumflexsmall",
        "hyphensuperior",
        "Gravesmall",
        "Asmall",
        "Bsmall",
        "Csmall",
        "Dsmall",
        "Esmall",
        "Fsmall",
        "Gsmall",
        "Hsmall",
        "Ismall",
        "Jsmall",
        "Ksmall",
        "Lsmall",
        "Msmall",
        "Nsmall",
        "Osmall",
        "Psmall",
        "Qsmall",
        "Rsmall",
        "Ssmall",
        "Tsmall",
        "Usmall",
        "Vsmall",
        "Wsmall",
        "Xsmall",
        "Ysmall",
        "Zsmall",
        "colonmonetary",
        "onefitted",
        "rupiah",
        "Tildesmall",
        "exclamdownsmall",
        "centoldstyle",
        "Lslashsmall",
        "Scaronsmall",
        "Zcaronsmall",
        "Dieresissmall",
        "Brevesmall",
        "Caronsmall",
        "Dotaccentsmall",
        "Macronsmall",
        "figuredash",
        "hypheninferior",
        "Ogoneksmall",
        "Ringsmall",
        "Cedillasmall",
        "questiondownsmall",
        "oneeighth",
        "threeeighths",
        "fiveeighths",
        "seveneighths",
        "onethird",
        "twothirds",
        "zerosuperior",
        "foursuperior",
        "fivesuperior",
        "sixsuperior",
        "sevensuperior",
        "eightsuperior",
        "ninesuperior",
        "zeroinferior",
        "oneinferior",
        "twoinferior",
        "threeinferior",
        "fourinferior",
        "fiveinferior",
        "sixinferior",
        "seveninferior",
        "eightinferior",
        "nineinferior",
        "centinferior",
        "dollarinferior",
        "periodinferior",
        "commainferior",
        "Agravesmall",
        "Aacutesmall",
        "Acircumflexsmall",
        "Atildesmall",
        "Adieresissmall",
        "Aringsmall",
        "AEsmall",
        "Ccedillasmall",
        "Egravesmall",
        "Eacutesmall",
        "Ecircumflexsmall",
        "Edieresissmall",
        "Igravesmall",
        "Iacutesmall",
        "Icircumflexsmall",
        "Idieresissmall",
        "Ethsmall",
        "Ntildesmall",
        "Ogravesmall",
        "Oacutesmall",
        "Ocircumflexsmall",
        "Otildesmall",
        "Odieresissmall",
        "OEsmall",
        "Oslashsmall",
        "Ugravesmall",
        "Uacutesmall",
        "Ucircumflexsmall",
        "Udieresissmall",
        "Yacutesmall",
        "Thornsmall",
        "Ydieresissmall",
        "001.000",
        "001.001",
        "001.002",
        "001.003",
        "Black",
        "Bold",
        "Book",
        "Light",
        "Medium",
        "Regular",
        "Roman",
        "Semibold"
      ];
      var cffStandardEncoding = [
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "space",
        "exclam",
        "quotedbl",
        "numbersign",
        "dollar",
        "percent",
        "ampersand",
        "quoteright",
        "parenleft",
        "parenright",
        "asterisk",
        "plus",
        "comma",
        "hyphen",
        "period",
        "slash",
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "colon",
        "semicolon",
        "less",
        "equal",
        "greater",
        "question",
        "at",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
        "Z",
        "bracketleft",
        "backslash",
        "bracketright",
        "asciicircum",
        "underscore",
        "quoteleft",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "braceleft",
        "bar",
        "braceright",
        "asciitilde",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "exclamdown",
        "cent",
        "sterling",
        "fraction",
        "yen",
        "florin",
        "section",
        "currency",
        "quotesingle",
        "quotedblleft",
        "guillemotleft",
        "guilsinglleft",
        "guilsinglright",
        "fi",
        "fl",
        "",
        "endash",
        "dagger",
        "daggerdbl",
        "periodcentered",
        "",
        "paragraph",
        "bullet",
        "quotesinglbase",
        "quotedblbase",
        "quotedblright",
        "guillemotright",
        "ellipsis",
        "perthousand",
        "",
        "questiondown",
        "",
        "grave",
        "acute",
        "circumflex",
        "tilde",
        "macron",
        "breve",
        "dotaccent",
        "dieresis",
        "",
        "ring",
        "cedilla",
        "",
        "hungarumlaut",
        "ogonek",
        "caron",
        "emdash",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "AE",
        "",
        "ordfeminine",
        "",
        "",
        "",
        "",
        "Lslash",
        "Oslash",
        "OE",
        "ordmasculine",
        "",
        "",
        "",
        "",
        "",
        "ae",
        "",
        "",
        "",
        "dotlessi",
        "",
        "",
        "lslash",
        "oslash",
        "oe",
        "germandbls"
      ];
      var cffExpertEncoding = [
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "space",
        "exclamsmall",
        "Hungarumlautsmall",
        "",
        "dollaroldstyle",
        "dollarsuperior",
        "ampersandsmall",
        "Acutesmall",
        "parenleftsuperior",
        "parenrightsuperior",
        "twodotenleader",
        "onedotenleader",
        "comma",
        "hyphen",
        "period",
        "fraction",
        "zerooldstyle",
        "oneoldstyle",
        "twooldstyle",
        "threeoldstyle",
        "fouroldstyle",
        "fiveoldstyle",
        "sixoldstyle",
        "sevenoldstyle",
        "eightoldstyle",
        "nineoldstyle",
        "colon",
        "semicolon",
        "commasuperior",
        "threequartersemdash",
        "periodsuperior",
        "questionsmall",
        "",
        "asuperior",
        "bsuperior",
        "centsuperior",
        "dsuperior",
        "esuperior",
        "",
        "",
        "isuperior",
        "",
        "",
        "lsuperior",
        "msuperior",
        "nsuperior",
        "osuperior",
        "",
        "",
        "rsuperior",
        "ssuperior",
        "tsuperior",
        "",
        "ff",
        "fi",
        "fl",
        "ffi",
        "ffl",
        "parenleftinferior",
        "",
        "parenrightinferior",
        "Circumflexsmall",
        "hyphensuperior",
        "Gravesmall",
        "Asmall",
        "Bsmall",
        "Csmall",
        "Dsmall",
        "Esmall",
        "Fsmall",
        "Gsmall",
        "Hsmall",
        "Ismall",
        "Jsmall",
        "Ksmall",
        "Lsmall",
        "Msmall",
        "Nsmall",
        "Osmall",
        "Psmall",
        "Qsmall",
        "Rsmall",
        "Ssmall",
        "Tsmall",
        "Usmall",
        "Vsmall",
        "Wsmall",
        "Xsmall",
        "Ysmall",
        "Zsmall",
        "colonmonetary",
        "onefitted",
        "rupiah",
        "Tildesmall",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "exclamdownsmall",
        "centoldstyle",
        "Lslashsmall",
        "",
        "",
        "Scaronsmall",
        "Zcaronsmall",
        "Dieresissmall",
        "Brevesmall",
        "Caronsmall",
        "",
        "Dotaccentsmall",
        "",
        "",
        "Macronsmall",
        "",
        "",
        "figuredash",
        "hypheninferior",
        "",
        "",
        "Ogoneksmall",
        "Ringsmall",
        "Cedillasmall",
        "",
        "",
        "",
        "onequarter",
        "onehalf",
        "threequarters",
        "questiondownsmall",
        "oneeighth",
        "threeeighths",
        "fiveeighths",
        "seveneighths",
        "onethird",
        "twothirds",
        "",
        "",
        "zerosuperior",
        "onesuperior",
        "twosuperior",
        "threesuperior",
        "foursuperior",
        "fivesuperior",
        "sixsuperior",
        "sevensuperior",
        "eightsuperior",
        "ninesuperior",
        "zeroinferior",
        "oneinferior",
        "twoinferior",
        "threeinferior",
        "fourinferior",
        "fiveinferior",
        "sixinferior",
        "seveninferior",
        "eightinferior",
        "nineinferior",
        "centinferior",
        "dollarinferior",
        "periodinferior",
        "commainferior",
        "Agravesmall",
        "Aacutesmall",
        "Acircumflexsmall",
        "Atildesmall",
        "Adieresissmall",
        "Aringsmall",
        "AEsmall",
        "Ccedillasmall",
        "Egravesmall",
        "Eacutesmall",
        "Ecircumflexsmall",
        "Edieresissmall",
        "Igravesmall",
        "Iacutesmall",
        "Icircumflexsmall",
        "Idieresissmall",
        "Ethsmall",
        "Ntildesmall",
        "Ogravesmall",
        "Oacutesmall",
        "Ocircumflexsmall",
        "Otildesmall",
        "Odieresissmall",
        "OEsmall",
        "Oslashsmall",
        "Ugravesmall",
        "Uacutesmall",
        "Ucircumflexsmall",
        "Udieresissmall",
        "Yacutesmall",
        "Thornsmall",
        "Ydieresissmall"
      ];
      var standardNames = [
        ".notdef",
        ".null",
        "nonmarkingreturn",
        "space",
        "exclam",
        "quotedbl",
        "numbersign",
        "dollar",
        "percent",
        "ampersand",
        "quotesingle",
        "parenleft",
        "parenright",
        "asterisk",
        "plus",
        "comma",
        "hyphen",
        "period",
        "slash",
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "colon",
        "semicolon",
        "less",
        "equal",
        "greater",
        "question",
        "at",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
        "T",
        "U",
        "V",
        "W",
        "X",
        "Y",
        "Z",
        "bracketleft",
        "backslash",
        "bracketright",
        "asciicircum",
        "underscore",
        "grave",
        "a",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
        "i",
        "j",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "q",
        "r",
        "s",
        "t",
        "u",
        "v",
        "w",
        "x",
        "y",
        "z",
        "braceleft",
        "bar",
        "braceright",
        "asciitilde",
        "Adieresis",
        "Aring",
        "Ccedilla",
        "Eacute",
        "Ntilde",
        "Odieresis",
        "Udieresis",
        "aacute",
        "agrave",
        "acircumflex",
        "adieresis",
        "atilde",
        "aring",
        "ccedilla",
        "eacute",
        "egrave",
        "ecircumflex",
        "edieresis",
        "iacute",
        "igrave",
        "icircumflex",
        "idieresis",
        "ntilde",
        "oacute",
        "ograve",
        "ocircumflex",
        "odieresis",
        "otilde",
        "uacute",
        "ugrave",
        "ucircumflex",
        "udieresis",
        "dagger",
        "degree",
        "cent",
        "sterling",
        "section",
        "bullet",
        "paragraph",
        "germandbls",
        "registered",
        "copyright",
        "trademark",
        "acute",
        "dieresis",
        "notequal",
        "AE",
        "Oslash",
        "infinity",
        "plusminus",
        "lessequal",
        "greaterequal",
        "yen",
        "mu",
        "partialdiff",
        "summation",
        "product",
        "pi",
        "integral",
        "ordfeminine",
        "ordmasculine",
        "Omega",
        "ae",
        "oslash",
        "questiondown",
        "exclamdown",
        "logicalnot",
        "radical",
        "florin",
        "approxequal",
        "Delta",
        "guillemotleft",
        "guillemotright",
        "ellipsis",
        "nonbreakingspace",
        "Agrave",
        "Atilde",
        "Otilde",
        "OE",
        "oe",
        "endash",
        "emdash",
        "quotedblleft",
        "quotedblright",
        "quoteleft",
        "quoteright",
        "divide",
        "lozenge",
        "ydieresis",
        "Ydieresis",
        "fraction",
        "currency",
        "guilsinglleft",
        "guilsinglright",
        "fi",
        "fl",
        "daggerdbl",
        "periodcentered",
        "quotesinglbase",
        "quotedblbase",
        "perthousand",
        "Acircumflex",
        "Ecircumflex",
        "Aacute",
        "Edieresis",
        "Egrave",
        "Iacute",
        "Icircumflex",
        "Idieresis",
        "Igrave",
        "Oacute",
        "Ocircumflex",
        "apple",
        "Ograve",
        "Uacute",
        "Ucircumflex",
        "Ugrave",
        "dotlessi",
        "circumflex",
        "tilde",
        "macron",
        "breve",
        "dotaccent",
        "ring",
        "cedilla",
        "hungarumlaut",
        "ogonek",
        "caron",
        "Lslash",
        "lslash",
        "Scaron",
        "scaron",
        "Zcaron",
        "zcaron",
        "brokenbar",
        "Eth",
        "eth",
        "Yacute",
        "yacute",
        "Thorn",
        "thorn",
        "minus",
        "multiply",
        "onesuperior",
        "twosuperior",
        "threesuperior",
        "onehalf",
        "onequarter",
        "threequarters",
        "franc",
        "Gbreve",
        "gbreve",
        "Idotaccent",
        "Scedilla",
        "scedilla",
        "Cacute",
        "cacute",
        "Ccaron",
        "ccaron",
        "dcroat"
      ];
      function DefaultEncoding(font) {
        this.font = font;
      }
      DefaultEncoding.prototype.charToGlyphIndex = function(c) {
        var code = c.codePointAt(0);
        var glyphs = this.font.glyphs;
        if (glyphs) {
          for (var i = 0; i < glyphs.length; i += 1) {
            var glyph = glyphs.get(i);
            for (var j = 0; j < glyph.unicodes.length; j += 1) {
              if (glyph.unicodes[j] === code) {
                return i;
              }
            }
          }
        }
        return null;
      };
      function CmapEncoding(cmap2) {
        this.cmap = cmap2;
      }
      CmapEncoding.prototype.charToGlyphIndex = function(c) {
        return this.cmap.glyphIndexMap[c.codePointAt(0)] || 0;
      };
      function CffEncoding(encoding, charset) {
        this.encoding = encoding;
        this.charset = charset;
      }
      CffEncoding.prototype.charToGlyphIndex = function(s) {
        var code = s.codePointAt(0);
        var charName = this.encoding[code];
        return this.charset.indexOf(charName);
      };
      function GlyphNames(post2) {
        switch (post2.version) {
          case 1:
            this.names = standardNames.slice();
            break;
          case 2:
            this.names = new Array(post2.numberOfGlyphs);
            for (var i = 0; i < post2.numberOfGlyphs; i++) {
              if (post2.glyphNameIndex[i] < standardNames.length) {
                this.names[i] = standardNames[post2.glyphNameIndex[i]];
              } else {
                this.names[i] = post2.names[post2.glyphNameIndex[i] - standardNames.length];
              }
            }
            break;
          case 2.5:
            this.names = new Array(post2.numberOfGlyphs);
            for (var i$1 = 0; i$1 < post2.numberOfGlyphs; i$1++) {
              this.names[i$1] = standardNames[i$1 + post2.glyphNameIndex[i$1]];
            }
            break;
          case 3:
            this.names = [];
            break;
          default:
            this.names = [];
            break;
        }
      }
      GlyphNames.prototype.nameToGlyphIndex = function(name) {
        return this.names.indexOf(name);
      };
      GlyphNames.prototype.glyphIndexToName = function(gid) {
        return this.names[gid];
      };
      function addGlyphNamesAll(font) {
        var glyph;
        var glyphIndexMap = font.tables.cmap.glyphIndexMap;
        var charCodes = Object.keys(glyphIndexMap);
        for (var i = 0; i < charCodes.length; i += 1) {
          var c = charCodes[i];
          var glyphIndex = glyphIndexMap[c];
          glyph = font.glyphs.get(glyphIndex);
          glyph.addUnicode(parseInt(c));
        }
        for (var i$1 = 0; i$1 < font.glyphs.length; i$1 += 1) {
          glyph = font.glyphs.get(i$1);
          if (font.cffEncoding) {
            if (font.isCIDFont) {
              glyph.name = "gid" + i$1;
            } else {
              glyph.name = font.cffEncoding.charset[i$1];
            }
          } else if (font.glyphNames.names) {
            glyph.name = font.glyphNames.glyphIndexToName(i$1);
          }
        }
      }
      function addGlyphNamesToUnicodeMap(font) {
        font._IndexToUnicodeMap = {};
        var glyphIndexMap = font.tables.cmap.glyphIndexMap;
        var charCodes = Object.keys(glyphIndexMap);
        for (var i = 0; i < charCodes.length; i += 1) {
          var c = charCodes[i];
          var glyphIndex = glyphIndexMap[c];
          if (font._IndexToUnicodeMap[glyphIndex] === void 0) {
            font._IndexToUnicodeMap[glyphIndex] = {
              unicodes: [parseInt(c)]
            };
          } else {
            font._IndexToUnicodeMap[glyphIndex].unicodes.push(parseInt(c));
          }
        }
      }
      function addGlyphNames(font, opt) {
        if (opt.lowMemory) {
          addGlyphNamesToUnicodeMap(font);
        } else {
          addGlyphNamesAll(font);
        }
      }
      function line(ctx, x1, y1, x2, y2) {
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      var draw = { line };
      function getPathDefinition(glyph, path) {
        var _path = path || new Path();
        return {
          configurable: true,
          get: function() {
            if (typeof _path === "function") {
              _path = _path();
            }
            return _path;
          },
          set: function(p) {
            _path = p;
          }
        };
      }
      function Glyph(options) {
        this.bindConstructorValues(options);
      }
      Glyph.prototype.bindConstructorValues = function(options) {
        this.index = options.index || 0;
        this.name = options.name || null;
        this.unicode = options.unicode || void 0;
        this.unicodes = options.unicodes || options.unicode !== void 0 ? [options.unicode] : [];
        if ("xMin" in options) {
          this.xMin = options.xMin;
        }
        if ("yMin" in options) {
          this.yMin = options.yMin;
        }
        if ("xMax" in options) {
          this.xMax = options.xMax;
        }
        if ("yMax" in options) {
          this.yMax = options.yMax;
        }
        if ("advanceWidth" in options) {
          this.advanceWidth = options.advanceWidth;
        }
        Object.defineProperty(this, "path", getPathDefinition(this, options.path));
      };
      Glyph.prototype.addUnicode = function(unicode) {
        if (this.unicodes.length === 0) {
          this.unicode = unicode;
        }
        this.unicodes.push(unicode);
      };
      Glyph.prototype.getBoundingBox = function() {
        return this.path.getBoundingBox();
      };
      Glyph.prototype.getPath = function(x, y, fontSize, options, font) {
        x = x !== void 0 ? x : 0;
        y = y !== void 0 ? y : 0;
        fontSize = fontSize !== void 0 ? fontSize : 72;
        var commands;
        var hPoints;
        if (!options) {
          options = {};
        }
        var xScale = options.xScale;
        var yScale = options.yScale;
        if (options.hinting && font && font.hinting) {
          hPoints = this.path && font.hinting.exec(this, fontSize);
        }
        if (hPoints) {
          commands = font.hinting.getCommands(hPoints);
          x = Math.round(x);
          y = Math.round(y);
          xScale = yScale = 1;
        } else {
          commands = this.path.commands;
          var scale = 1 / (this.path.unitsPerEm || 1e3) * fontSize;
          if (xScale === void 0) {
            xScale = scale;
          }
          if (yScale === void 0) {
            yScale = scale;
          }
        }
        var p = new Path();
        for (var i = 0; i < commands.length; i += 1) {
          var cmd = commands[i];
          if (cmd.type === "M") {
            p.moveTo(x + cmd.x * xScale, y + -cmd.y * yScale);
          } else if (cmd.type === "L") {
            p.lineTo(x + cmd.x * xScale, y + -cmd.y * yScale);
          } else if (cmd.type === "Q") {
            p.quadraticCurveTo(
              x + cmd.x1 * xScale,
              y + -cmd.y1 * yScale,
              x + cmd.x * xScale,
              y + -cmd.y * yScale
            );
          } else if (cmd.type === "C") {
            p.curveTo(
              x + cmd.x1 * xScale,
              y + -cmd.y1 * yScale,
              x + cmd.x2 * xScale,
              y + -cmd.y2 * yScale,
              x + cmd.x * xScale,
              y + -cmd.y * yScale
            );
          } else if (cmd.type === "Z") {
            p.closePath();
          }
        }
        return p;
      };
      Glyph.prototype.getContours = function() {
        if (this.points === void 0) {
          return [];
        }
        var contours = [];
        var currentContour = [];
        for (var i = 0; i < this.points.length; i += 1) {
          var pt = this.points[i];
          currentContour.push(pt);
          if (pt.lastPointOfContour) {
            contours.push(currentContour);
            currentContour = [];
          }
        }
        check.argument(currentContour.length === 0, "There are still points left in the current contour.");
        return contours;
      };
      Glyph.prototype.getMetrics = function() {
        var commands = this.path.commands;
        var xCoords = [];
        var yCoords = [];
        for (var i = 0; i < commands.length; i += 1) {
          var cmd = commands[i];
          if (cmd.type !== "Z") {
            xCoords.push(cmd.x);
            yCoords.push(cmd.y);
          }
          if (cmd.type === "Q" || cmd.type === "C") {
            xCoords.push(cmd.x1);
            yCoords.push(cmd.y1);
          }
          if (cmd.type === "C") {
            xCoords.push(cmd.x2);
            yCoords.push(cmd.y2);
          }
        }
        var metrics = {
          xMin: Math.min.apply(null, xCoords),
          yMin: Math.min.apply(null, yCoords),
          xMax: Math.max.apply(null, xCoords),
          yMax: Math.max.apply(null, yCoords),
          leftSideBearing: this.leftSideBearing
        };
        if (!isFinite(metrics.xMin)) {
          metrics.xMin = 0;
        }
        if (!isFinite(metrics.xMax)) {
          metrics.xMax = this.advanceWidth;
        }
        if (!isFinite(metrics.yMin)) {
          metrics.yMin = 0;
        }
        if (!isFinite(metrics.yMax)) {
          metrics.yMax = 0;
        }
        metrics.rightSideBearing = this.advanceWidth - metrics.leftSideBearing - (metrics.xMax - metrics.xMin);
        return metrics;
      };
      Glyph.prototype.draw = function(ctx, x, y, fontSize, options) {
        this.getPath(x, y, fontSize, options).draw(ctx);
      };
      Glyph.prototype.drawPoints = function(ctx, x, y, fontSize) {
        function drawCircles(l, x2, y2, scale2) {
          ctx.beginPath();
          for (var j = 0; j < l.length; j += 1) {
            ctx.moveTo(x2 + l[j].x * scale2, y2 + l[j].y * scale2);
            ctx.arc(x2 + l[j].x * scale2, y2 + l[j].y * scale2, 2, 0, Math.PI * 2, false);
          }
          ctx.closePath();
          ctx.fill();
        }
        x = x !== void 0 ? x : 0;
        y = y !== void 0 ? y : 0;
        fontSize = fontSize !== void 0 ? fontSize : 24;
        var scale = 1 / this.path.unitsPerEm * fontSize;
        var blueCircles = [];
        var redCircles = [];
        var path = this.path;
        for (var i = 0; i < path.commands.length; i += 1) {
          var cmd = path.commands[i];
          if (cmd.x !== void 0) {
            blueCircles.push({ x: cmd.x, y: -cmd.y });
          }
          if (cmd.x1 !== void 0) {
            redCircles.push({ x: cmd.x1, y: -cmd.y1 });
          }
          if (cmd.x2 !== void 0) {
            redCircles.push({ x: cmd.x2, y: -cmd.y2 });
          }
        }
        ctx.fillStyle = "blue";
        drawCircles(blueCircles, x, y, scale);
        ctx.fillStyle = "red";
        drawCircles(redCircles, x, y, scale);
      };
      Glyph.prototype.drawMetrics = function(ctx, x, y, fontSize) {
        var scale;
        x = x !== void 0 ? x : 0;
        y = y !== void 0 ? y : 0;
        fontSize = fontSize !== void 0 ? fontSize : 24;
        scale = 1 / this.path.unitsPerEm * fontSize;
        ctx.lineWidth = 1;
        ctx.strokeStyle = "black";
        draw.line(ctx, x, -1e4, x, 1e4);
        draw.line(ctx, -1e4, y, 1e4, y);
        var xMin = this.xMin || 0;
        var yMin = this.yMin || 0;
        var xMax = this.xMax || 0;
        var yMax = this.yMax || 0;
        var advanceWidth = this.advanceWidth || 0;
        ctx.strokeStyle = "blue";
        draw.line(ctx, x + xMin * scale, -1e4, x + xMin * scale, 1e4);
        draw.line(ctx, x + xMax * scale, -1e4, x + xMax * scale, 1e4);
        draw.line(ctx, -1e4, y + -yMin * scale, 1e4, y + -yMin * scale);
        draw.line(ctx, -1e4, y + -yMax * scale, 1e4, y + -yMax * scale);
        ctx.strokeStyle = "green";
        draw.line(ctx, x + advanceWidth * scale, -1e4, x + advanceWidth * scale, 1e4);
      };
      function defineDependentProperty(glyph, externalName, internalName) {
        Object.defineProperty(glyph, externalName, {
          get: function() {
            glyph.path;
            return glyph[internalName];
          },
          set: function(newValue) {
            glyph[internalName] = newValue;
          },
          enumerable: true,
          configurable: true
        });
      }
      function GlyphSet(font, glyphs) {
        this.font = font;
        this.glyphs = {};
        if (Array.isArray(glyphs)) {
          for (var i = 0; i < glyphs.length; i++) {
            var glyph = glyphs[i];
            glyph.path.unitsPerEm = font.unitsPerEm;
            this.glyphs[i] = glyph;
          }
        }
        this.length = glyphs && glyphs.length || 0;
      }
      GlyphSet.prototype.get = function(index) {
        if (this.glyphs[index] === void 0) {
          this.font._push(index);
          if (typeof this.glyphs[index] === "function") {
            this.glyphs[index] = this.glyphs[index]();
          }
          var glyph = this.glyphs[index];
          var unicodeObj = this.font._IndexToUnicodeMap[index];
          if (unicodeObj) {
            for (var j = 0; j < unicodeObj.unicodes.length; j++) {
              glyph.addUnicode(unicodeObj.unicodes[j]);
            }
          }
          if (this.font.cffEncoding) {
            if (this.font.isCIDFont) {
              glyph.name = "gid" + index;
            } else {
              glyph.name = this.font.cffEncoding.charset[index];
            }
          } else if (this.font.glyphNames.names) {
            glyph.name = this.font.glyphNames.glyphIndexToName(index);
          }
          this.glyphs[index].advanceWidth = this.font._hmtxTableData[index].advanceWidth;
          this.glyphs[index].leftSideBearing = this.font._hmtxTableData[index].leftSideBearing;
        } else {
          if (typeof this.glyphs[index] === "function") {
            this.glyphs[index] = this.glyphs[index]();
          }
        }
        return this.glyphs[index];
      };
      GlyphSet.prototype.push = function(index, loader) {
        this.glyphs[index] = loader;
        this.length++;
      };
      function glyphLoader(font, index) {
        return new Glyph({ index, font });
      }
      function ttfGlyphLoader(font, index, parseGlyph2, data, position, buildPath2) {
        return function() {
          var glyph = new Glyph({ index, font });
          glyph.path = function() {
            parseGlyph2(glyph, data, position);
            var path = buildPath2(font.glyphs, glyph);
            path.unitsPerEm = font.unitsPerEm;
            return path;
          };
          defineDependentProperty(glyph, "xMin", "_xMin");
          defineDependentProperty(glyph, "xMax", "_xMax");
          defineDependentProperty(glyph, "yMin", "_yMin");
          defineDependentProperty(glyph, "yMax", "_yMax");
          return glyph;
        };
      }
      function cffGlyphLoader(font, index, parseCFFCharstring2, charstring) {
        return function() {
          var glyph = new Glyph({ index, font });
          glyph.path = function() {
            var path = parseCFFCharstring2(font, glyph, charstring);
            path.unitsPerEm = font.unitsPerEm;
            return path;
          };
          return glyph;
        };
      }
      var glyphset = { GlyphSet, glyphLoader, ttfGlyphLoader, cffGlyphLoader };
      function equals(a, b2) {
        if (a === b2) {
          return true;
        } else if (Array.isArray(a) && Array.isArray(b2)) {
          if (a.length !== b2.length) {
            return false;
          }
          for (var i = 0; i < a.length; i += 1) {
            if (!equals(a[i], b2[i])) {
              return false;
            }
          }
          return true;
        } else {
          return false;
        }
      }
      function calcCFFSubroutineBias(subrs) {
        var bias;
        if (subrs.length < 1240) {
          bias = 107;
        } else if (subrs.length < 33900) {
          bias = 1131;
        } else {
          bias = 32768;
        }
        return bias;
      }
      function parseCFFIndex(data, start, conversionFn) {
        var offsets = [];
        var objects = [];
        var count = parse2.getCard16(data, start);
        var objectOffset;
        var endOffset;
        if (count !== 0) {
          var offsetSize = parse2.getByte(data, start + 2);
          objectOffset = start + (count + 1) * offsetSize + 2;
          var pos = start + 3;
          for (var i = 0; i < count + 1; i += 1) {
            offsets.push(parse2.getOffset(data, pos, offsetSize));
            pos += offsetSize;
          }
          endOffset = objectOffset + offsets[count];
        } else {
          endOffset = start + 2;
        }
        for (var i$1 = 0; i$1 < offsets.length - 1; i$1 += 1) {
          var value = parse2.getBytes(data, objectOffset + offsets[i$1], objectOffset + offsets[i$1 + 1]);
          if (conversionFn) {
            value = conversionFn(value);
          }
          objects.push(value);
        }
        return { objects, startOffset: start, endOffset };
      }
      function parseCFFIndexLowMemory(data, start) {
        var offsets = [];
        var count = parse2.getCard16(data, start);
        var objectOffset;
        var endOffset;
        if (count !== 0) {
          var offsetSize = parse2.getByte(data, start + 2);
          objectOffset = start + (count + 1) * offsetSize + 2;
          var pos = start + 3;
          for (var i = 0; i < count + 1; i += 1) {
            offsets.push(parse2.getOffset(data, pos, offsetSize));
            pos += offsetSize;
          }
          endOffset = objectOffset + offsets[count];
        } else {
          endOffset = start + 2;
        }
        return { offsets, startOffset: start, endOffset };
      }
      function getCffIndexObject(i, offsets, data, start, conversionFn) {
        var count = parse2.getCard16(data, start);
        var objectOffset = 0;
        if (count !== 0) {
          var offsetSize = parse2.getByte(data, start + 2);
          objectOffset = start + (count + 1) * offsetSize + 2;
        }
        var value = parse2.getBytes(data, objectOffset + offsets[i], objectOffset + offsets[i + 1]);
        if (conversionFn) {
          value = conversionFn(value);
        }
        return value;
      }
      function parseFloatOperand(parser) {
        var s = "";
        var eof = 15;
        var lookup = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "E", "E-", null, "-"];
        while (true) {
          var b2 = parser.parseByte();
          var n1 = b2 >> 4;
          var n2 = b2 & 15;
          if (n1 === eof) {
            break;
          }
          s += lookup[n1];
          if (n2 === eof) {
            break;
          }
          s += lookup[n2];
        }
        return parseFloat(s);
      }
      function parseOperand(parser, b0) {
        var b1;
        var b2;
        var b3;
        var b4;
        if (b0 === 28) {
          b1 = parser.parseByte();
          b2 = parser.parseByte();
          return b1 << 8 | b2;
        }
        if (b0 === 29) {
          b1 = parser.parseByte();
          b2 = parser.parseByte();
          b3 = parser.parseByte();
          b4 = parser.parseByte();
          return b1 << 24 | b2 << 16 | b3 << 8 | b4;
        }
        if (b0 === 30) {
          return parseFloatOperand(parser);
        }
        if (b0 >= 32 && b0 <= 246) {
          return b0 - 139;
        }
        if (b0 >= 247 && b0 <= 250) {
          b1 = parser.parseByte();
          return (b0 - 247) * 256 + b1 + 108;
        }
        if (b0 >= 251 && b0 <= 254) {
          b1 = parser.parseByte();
          return -(b0 - 251) * 256 - b1 - 108;
        }
        throw new Error("Invalid b0 " + b0);
      }
      function entriesToObject(entries) {
        var o = {};
        for (var i = 0; i < entries.length; i += 1) {
          var key = entries[i][0];
          var values2 = entries[i][1];
          var value = void 0;
          if (values2.length === 1) {
            value = values2[0];
          } else {
            value = values2;
          }
          if (o.hasOwnProperty(key) && !isNaN(o[key])) {
            throw new Error("Object " + o + " already has key " + key);
          }
          o[key] = value;
        }
        return o;
      }
      function parseCFFDict(data, start, size2) {
        start = start !== void 0 ? start : 0;
        var parser = new parse2.Parser(data, start);
        var entries = [];
        var operands = [];
        size2 = size2 !== void 0 ? size2 : data.length;
        while (parser.relativeOffset < size2) {
          var op = parser.parseByte();
          if (op <= 21) {
            if (op === 12) {
              op = 1200 + parser.parseByte();
            }
            entries.push([op, operands]);
            operands = [];
          } else {
            operands.push(parseOperand(parser, op));
          }
        }
        return entriesToObject(entries);
      }
      function getCFFString(strings, index) {
        if (index <= 390) {
          index = cffStandardStrings[index];
        } else {
          index = strings[index - 391];
        }
        return index;
      }
      function interpretDict(dict, meta2, strings) {
        var newDict = {};
        var value;
        for (var i = 0; i < meta2.length; i += 1) {
          var m = meta2[i];
          if (Array.isArray(m.type)) {
            var values2 = [];
            values2.length = m.type.length;
            for (var j = 0; j < m.type.length; j++) {
              value = dict[m.op] !== void 0 ? dict[m.op][j] : void 0;
              if (value === void 0) {
                value = m.value !== void 0 && m.value[j] !== void 0 ? m.value[j] : null;
              }
              if (m.type[j] === "SID") {
                value = getCFFString(strings, value);
              }
              values2[j] = value;
            }
            newDict[m.name] = values2;
          } else {
            value = dict[m.op];
            if (value === void 0) {
              value = m.value !== void 0 ? m.value : null;
            }
            if (m.type === "SID") {
              value = getCFFString(strings, value);
            }
            newDict[m.name] = value;
          }
        }
        return newDict;
      }
      function parseCFFHeader(data, start) {
        var header = {};
        header.formatMajor = parse2.getCard8(data, start);
        header.formatMinor = parse2.getCard8(data, start + 1);
        header.size = parse2.getCard8(data, start + 2);
        header.offsetSize = parse2.getCard8(data, start + 3);
        header.startOffset = start;
        header.endOffset = start + 4;
        return header;
      }
      var TOP_DICT_META = [
        { name: "version", op: 0, type: "SID" },
        { name: "notice", op: 1, type: "SID" },
        { name: "copyright", op: 1200, type: "SID" },
        { name: "fullName", op: 2, type: "SID" },
        { name: "familyName", op: 3, type: "SID" },
        { name: "weight", op: 4, type: "SID" },
        { name: "isFixedPitch", op: 1201, type: "number", value: 0 },
        { name: "italicAngle", op: 1202, type: "number", value: 0 },
        { name: "underlinePosition", op: 1203, type: "number", value: -100 },
        { name: "underlineThickness", op: 1204, type: "number", value: 50 },
        { name: "paintType", op: 1205, type: "number", value: 0 },
        { name: "charstringType", op: 1206, type: "number", value: 2 },
        {
          name: "fontMatrix",
          op: 1207,
          type: ["real", "real", "real", "real", "real", "real"],
          value: [1e-3, 0, 0, 1e-3, 0, 0]
        },
        { name: "uniqueId", op: 13, type: "number" },
        { name: "fontBBox", op: 5, type: ["number", "number", "number", "number"], value: [0, 0, 0, 0] },
        { name: "strokeWidth", op: 1208, type: "number", value: 0 },
        { name: "xuid", op: 14, type: [], value: null },
        { name: "charset", op: 15, type: "offset", value: 0 },
        { name: "encoding", op: 16, type: "offset", value: 0 },
        { name: "charStrings", op: 17, type: "offset", value: 0 },
        { name: "private", op: 18, type: ["number", "offset"], value: [0, 0] },
        { name: "ros", op: 1230, type: ["SID", "SID", "number"] },
        { name: "cidFontVersion", op: 1231, type: "number", value: 0 },
        { name: "cidFontRevision", op: 1232, type: "number", value: 0 },
        { name: "cidFontType", op: 1233, type: "number", value: 0 },
        { name: "cidCount", op: 1234, type: "number", value: 8720 },
        { name: "uidBase", op: 1235, type: "number" },
        { name: "fdArray", op: 1236, type: "offset" },
        { name: "fdSelect", op: 1237, type: "offset" },
        { name: "fontName", op: 1238, type: "SID" }
      ];
      var PRIVATE_DICT_META = [
        { name: "subrs", op: 19, type: "offset", value: 0 },
        { name: "defaultWidthX", op: 20, type: "number", value: 0 },
        { name: "nominalWidthX", op: 21, type: "number", value: 0 }
      ];
      function parseCFFTopDict(data, strings) {
        var dict = parseCFFDict(data, 0, data.byteLength);
        return interpretDict(dict, TOP_DICT_META, strings);
      }
      function parseCFFPrivateDict(data, start, size2, strings) {
        var dict = parseCFFDict(data, start, size2);
        return interpretDict(dict, PRIVATE_DICT_META, strings);
      }
      function gatherCFFTopDicts(data, start, cffIndex, strings) {
        var topDictArray = [];
        for (var iTopDict = 0; iTopDict < cffIndex.length; iTopDict += 1) {
          var topDictData = new DataView(new Uint8Array(cffIndex[iTopDict]).buffer);
          var topDict = parseCFFTopDict(topDictData, strings);
          topDict._subrs = [];
          topDict._subrsBias = 0;
          topDict._defaultWidthX = 0;
          topDict._nominalWidthX = 0;
          var privateSize = topDict.private[0];
          var privateOffset = topDict.private[1];
          if (privateSize !== 0 && privateOffset !== 0) {
            var privateDict = parseCFFPrivateDict(data, privateOffset + start, privateSize, strings);
            topDict._defaultWidthX = privateDict.defaultWidthX;
            topDict._nominalWidthX = privateDict.nominalWidthX;
            if (privateDict.subrs !== 0) {
              var subrOffset = privateOffset + privateDict.subrs;
              var subrIndex = parseCFFIndex(data, subrOffset + start);
              topDict._subrs = subrIndex.objects;
              topDict._subrsBias = calcCFFSubroutineBias(topDict._subrs);
            }
            topDict._privateDict = privateDict;
          }
          topDictArray.push(topDict);
        }
        return topDictArray;
      }
      function parseCFFCharset(data, start, nGlyphs, strings) {
        var sid;
        var count;
        var parser = new parse2.Parser(data, start);
        nGlyphs -= 1;
        var charset = [".notdef"];
        var format = parser.parseCard8();
        if (format === 0) {
          for (var i = 0; i < nGlyphs; i += 1) {
            sid = parser.parseSID();
            charset.push(getCFFString(strings, sid));
          }
        } else if (format === 1) {
          while (charset.length <= nGlyphs) {
            sid = parser.parseSID();
            count = parser.parseCard8();
            for (var i$1 = 0; i$1 <= count; i$1 += 1) {
              charset.push(getCFFString(strings, sid));
              sid += 1;
            }
          }
        } else if (format === 2) {
          while (charset.length <= nGlyphs) {
            sid = parser.parseSID();
            count = parser.parseCard16();
            for (var i$2 = 0; i$2 <= count; i$2 += 1) {
              charset.push(getCFFString(strings, sid));
              sid += 1;
            }
          }
        } else {
          throw new Error("Unknown charset format " + format);
        }
        return charset;
      }
      function parseCFFEncoding(data, start, charset) {
        var code;
        var enc = {};
        var parser = new parse2.Parser(data, start);
        var format = parser.parseCard8();
        if (format === 0) {
          var nCodes = parser.parseCard8();
          for (var i = 0; i < nCodes; i += 1) {
            code = parser.parseCard8();
            enc[code] = i;
          }
        } else if (format === 1) {
          var nRanges = parser.parseCard8();
          code = 1;
          for (var i$1 = 0; i$1 < nRanges; i$1 += 1) {
            var first = parser.parseCard8();
            var nLeft = parser.parseCard8();
            for (var j = first; j <= first + nLeft; j += 1) {
              enc[j] = code;
              code += 1;
            }
          }
        } else {
          throw new Error("Unknown encoding format " + format);
        }
        return new CffEncoding(enc, charset);
      }
      function parseCFFCharstring(font, glyph, code) {
        var c1x;
        var c1y;
        var c2x;
        var c2y;
        var p = new Path();
        var stack = [];
        var nStems = 0;
        var haveWidth = false;
        var open = false;
        var x = 0;
        var y = 0;
        var subrs;
        var subrsBias;
        var defaultWidthX;
        var nominalWidthX;
        if (font.isCIDFont) {
          var fdIndex = font.tables.cff.topDict._fdSelect[glyph.index];
          var fdDict = font.tables.cff.topDict._fdArray[fdIndex];
          subrs = fdDict._subrs;
          subrsBias = fdDict._subrsBias;
          defaultWidthX = fdDict._defaultWidthX;
          nominalWidthX = fdDict._nominalWidthX;
        } else {
          subrs = font.tables.cff.topDict._subrs;
          subrsBias = font.tables.cff.topDict._subrsBias;
          defaultWidthX = font.tables.cff.topDict._defaultWidthX;
          nominalWidthX = font.tables.cff.topDict._nominalWidthX;
        }
        var width = defaultWidthX;
        function newContour(x2, y2) {
          if (open) {
            p.closePath();
          }
          p.moveTo(x2, y2);
          open = true;
        }
        function parseStems() {
          var hasWidthArg;
          hasWidthArg = stack.length % 2 !== 0;
          if (hasWidthArg && !haveWidth) {
            width = stack.shift() + nominalWidthX;
          }
          nStems += stack.length >> 1;
          stack.length = 0;
          haveWidth = true;
        }
        function parse3(code2) {
          var b1;
          var b2;
          var b3;
          var b4;
          var codeIndex;
          var subrCode;
          var jpx;
          var jpy;
          var c3x;
          var c3y;
          var c4x;
          var c4y;
          var i = 0;
          while (i < code2.length) {
            var v = code2[i];
            i += 1;
            switch (v) {
              case 1:
                parseStems();
                break;
              case 3:
                parseStems();
                break;
              case 4:
                if (stack.length > 1 && !haveWidth) {
                  width = stack.shift() + nominalWidthX;
                  haveWidth = true;
                }
                y += stack.pop();
                newContour(x, y);
                break;
              case 5:
                while (stack.length > 0) {
                  x += stack.shift();
                  y += stack.shift();
                  p.lineTo(x, y);
                }
                break;
              case 6:
                while (stack.length > 0) {
                  x += stack.shift();
                  p.lineTo(x, y);
                  if (stack.length === 0) {
                    break;
                  }
                  y += stack.shift();
                  p.lineTo(x, y);
                }
                break;
              case 7:
                while (stack.length > 0) {
                  y += stack.shift();
                  p.lineTo(x, y);
                  if (stack.length === 0) {
                    break;
                  }
                  x += stack.shift();
                  p.lineTo(x, y);
                }
                break;
              case 8:
                while (stack.length > 0) {
                  c1x = x + stack.shift();
                  c1y = y + stack.shift();
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x + stack.shift();
                  y = c2y + stack.shift();
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                break;
              case 10:
                codeIndex = stack.pop() + subrsBias;
                subrCode = subrs[codeIndex];
                if (subrCode) {
                  parse3(subrCode);
                }
                break;
              case 11:
                return;
              case 12:
                v = code2[i];
                i += 1;
                switch (v) {
                  case 35:
                    c1x = x + stack.shift();
                    c1y = y + stack.shift();
                    c2x = c1x + stack.shift();
                    c2y = c1y + stack.shift();
                    jpx = c2x + stack.shift();
                    jpy = c2y + stack.shift();
                    c3x = jpx + stack.shift();
                    c3y = jpy + stack.shift();
                    c4x = c3x + stack.shift();
                    c4y = c3y + stack.shift();
                    x = c4x + stack.shift();
                    y = c4y + stack.shift();
                    stack.shift();
                    p.curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
                    p.curveTo(c3x, c3y, c4x, c4y, x, y);
                    break;
                  case 34:
                    c1x = x + stack.shift();
                    c1y = y;
                    c2x = c1x + stack.shift();
                    c2y = c1y + stack.shift();
                    jpx = c2x + stack.shift();
                    jpy = c2y;
                    c3x = jpx + stack.shift();
                    c3y = c2y;
                    c4x = c3x + stack.shift();
                    c4y = y;
                    x = c4x + stack.shift();
                    p.curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
                    p.curveTo(c3x, c3y, c4x, c4y, x, y);
                    break;
                  case 36:
                    c1x = x + stack.shift();
                    c1y = y + stack.shift();
                    c2x = c1x + stack.shift();
                    c2y = c1y + stack.shift();
                    jpx = c2x + stack.shift();
                    jpy = c2y;
                    c3x = jpx + stack.shift();
                    c3y = c2y;
                    c4x = c3x + stack.shift();
                    c4y = c3y + stack.shift();
                    x = c4x + stack.shift();
                    p.curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
                    p.curveTo(c3x, c3y, c4x, c4y, x, y);
                    break;
                  case 37:
                    c1x = x + stack.shift();
                    c1y = y + stack.shift();
                    c2x = c1x + stack.shift();
                    c2y = c1y + stack.shift();
                    jpx = c2x + stack.shift();
                    jpy = c2y + stack.shift();
                    c3x = jpx + stack.shift();
                    c3y = jpy + stack.shift();
                    c4x = c3x + stack.shift();
                    c4y = c3y + stack.shift();
                    if (Math.abs(c4x - x) > Math.abs(c4y - y)) {
                      x = c4x + stack.shift();
                    } else {
                      y = c4y + stack.shift();
                    }
                    p.curveTo(c1x, c1y, c2x, c2y, jpx, jpy);
                    p.curveTo(c3x, c3y, c4x, c4y, x, y);
                    break;
                  default:
                    console.log("Glyph " + glyph.index + ": unknown operator 1200" + v);
                    stack.length = 0;
                }
                break;
              case 14:
                if (stack.length > 0 && !haveWidth) {
                  width = stack.shift() + nominalWidthX;
                  haveWidth = true;
                }
                if (open) {
                  p.closePath();
                  open = false;
                }
                break;
              case 18:
                parseStems();
                break;
              case 19:
              // hintmask
              case 20:
                parseStems();
                i += nStems + 7 >> 3;
                break;
              case 21:
                if (stack.length > 2 && !haveWidth) {
                  width = stack.shift() + nominalWidthX;
                  haveWidth = true;
                }
                y += stack.pop();
                x += stack.pop();
                newContour(x, y);
                break;
              case 22:
                if (stack.length > 1 && !haveWidth) {
                  width = stack.shift() + nominalWidthX;
                  haveWidth = true;
                }
                x += stack.pop();
                newContour(x, y);
                break;
              case 23:
                parseStems();
                break;
              case 24:
                while (stack.length > 2) {
                  c1x = x + stack.shift();
                  c1y = y + stack.shift();
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x + stack.shift();
                  y = c2y + stack.shift();
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                x += stack.shift();
                y += stack.shift();
                p.lineTo(x, y);
                break;
              case 25:
                while (stack.length > 6) {
                  x += stack.shift();
                  y += stack.shift();
                  p.lineTo(x, y);
                }
                c1x = x + stack.shift();
                c1y = y + stack.shift();
                c2x = c1x + stack.shift();
                c2y = c1y + stack.shift();
                x = c2x + stack.shift();
                y = c2y + stack.shift();
                p.curveTo(c1x, c1y, c2x, c2y, x, y);
                break;
              case 26:
                if (stack.length % 2) {
                  x += stack.shift();
                }
                while (stack.length > 0) {
                  c1x = x;
                  c1y = y + stack.shift();
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x;
                  y = c2y + stack.shift();
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                break;
              case 27:
                if (stack.length % 2) {
                  y += stack.shift();
                }
                while (stack.length > 0) {
                  c1x = x + stack.shift();
                  c1y = y;
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x + stack.shift();
                  y = c2y;
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                break;
              case 28:
                b1 = code2[i];
                b2 = code2[i + 1];
                stack.push((b1 << 24 | b2 << 16) >> 16);
                i += 2;
                break;
              case 29:
                codeIndex = stack.pop() + font.gsubrsBias;
                subrCode = font.gsubrs[codeIndex];
                if (subrCode) {
                  parse3(subrCode);
                }
                break;
              case 30:
                while (stack.length > 0) {
                  c1x = x;
                  c1y = y + stack.shift();
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x + stack.shift();
                  y = c2y + (stack.length === 1 ? stack.shift() : 0);
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                  if (stack.length === 0) {
                    break;
                  }
                  c1x = x + stack.shift();
                  c1y = y;
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  y = c2y + stack.shift();
                  x = c2x + (stack.length === 1 ? stack.shift() : 0);
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                break;
              case 31:
                while (stack.length > 0) {
                  c1x = x + stack.shift();
                  c1y = y;
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  y = c2y + stack.shift();
                  x = c2x + (stack.length === 1 ? stack.shift() : 0);
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                  if (stack.length === 0) {
                    break;
                  }
                  c1x = x;
                  c1y = y + stack.shift();
                  c2x = c1x + stack.shift();
                  c2y = c1y + stack.shift();
                  x = c2x + stack.shift();
                  y = c2y + (stack.length === 1 ? stack.shift() : 0);
                  p.curveTo(c1x, c1y, c2x, c2y, x, y);
                }
                break;
              default:
                if (v < 32) {
                  console.log("Glyph " + glyph.index + ": unknown operator " + v);
                } else if (v < 247) {
                  stack.push(v - 139);
                } else if (v < 251) {
                  b1 = code2[i];
                  i += 1;
                  stack.push((v - 247) * 256 + b1 + 108);
                } else if (v < 255) {
                  b1 = code2[i];
                  i += 1;
                  stack.push(-(v - 251) * 256 - b1 - 108);
                } else {
                  b1 = code2[i];
                  b2 = code2[i + 1];
                  b3 = code2[i + 2];
                  b4 = code2[i + 3];
                  i += 4;
                  stack.push((b1 << 24 | b2 << 16 | b3 << 8 | b4) / 65536);
                }
            }
          }
        }
        parse3(code);
        glyph.advanceWidth = width;
        return p;
      }
      function parseCFFFDSelect(data, start, nGlyphs, fdArrayCount) {
        var fdSelect = [];
        var fdIndex;
        var parser = new parse2.Parser(data, start);
        var format = parser.parseCard8();
        if (format === 0) {
          for (var iGid = 0; iGid < nGlyphs; iGid++) {
            fdIndex = parser.parseCard8();
            if (fdIndex >= fdArrayCount) {
              throw new Error("CFF table CID Font FDSelect has bad FD index value " + fdIndex + " (FD count " + fdArrayCount + ")");
            }
            fdSelect.push(fdIndex);
          }
        } else if (format === 3) {
          var nRanges = parser.parseCard16();
          var first = parser.parseCard16();
          if (first !== 0) {
            throw new Error("CFF Table CID Font FDSelect format 3 range has bad initial GID " + first);
          }
          var next;
          for (var iRange = 0; iRange < nRanges; iRange++) {
            fdIndex = parser.parseCard8();
            next = parser.parseCard16();
            if (fdIndex >= fdArrayCount) {
              throw new Error("CFF table CID Font FDSelect has bad FD index value " + fdIndex + " (FD count " + fdArrayCount + ")");
            }
            if (next > nGlyphs) {
              throw new Error("CFF Table CID Font FDSelect format 3 range has bad GID " + next);
            }
            for (; first < next; first++) {
              fdSelect.push(fdIndex);
            }
            first = next;
          }
          if (next !== nGlyphs) {
            throw new Error("CFF Table CID Font FDSelect format 3 range has bad final GID " + next);
          }
        } else {
          throw new Error("CFF Table CID Font FDSelect table has unsupported format " + format);
        }
        return fdSelect;
      }
      function parseCFFTable(data, start, font, opt) {
        font.tables.cff = {};
        var header = parseCFFHeader(data, start);
        var nameIndex = parseCFFIndex(data, header.endOffset, parse2.bytesToString);
        var topDictIndex = parseCFFIndex(data, nameIndex.endOffset);
        var stringIndex = parseCFFIndex(data, topDictIndex.endOffset, parse2.bytesToString);
        var globalSubrIndex = parseCFFIndex(data, stringIndex.endOffset);
        font.gsubrs = globalSubrIndex.objects;
        font.gsubrsBias = calcCFFSubroutineBias(font.gsubrs);
        var topDictArray = gatherCFFTopDicts(data, start, topDictIndex.objects, stringIndex.objects);
        if (topDictArray.length !== 1) {
          throw new Error("CFF table has too many fonts in 'FontSet' - count of fonts NameIndex.length = " + topDictArray.length);
        }
        var topDict = topDictArray[0];
        font.tables.cff.topDict = topDict;
        if (topDict._privateDict) {
          font.defaultWidthX = topDict._privateDict.defaultWidthX;
          font.nominalWidthX = topDict._privateDict.nominalWidthX;
        }
        if (topDict.ros[0] !== void 0 && topDict.ros[1] !== void 0) {
          font.isCIDFont = true;
        }
        if (font.isCIDFont) {
          var fdArrayOffset = topDict.fdArray;
          var fdSelectOffset = topDict.fdSelect;
          if (fdArrayOffset === 0 || fdSelectOffset === 0) {
            throw new Error("Font is marked as a CID font, but FDArray and/or FDSelect information is missing");
          }
          fdArrayOffset += start;
          var fdArrayIndex = parseCFFIndex(data, fdArrayOffset);
          var fdArray = gatherCFFTopDicts(data, start, fdArrayIndex.objects, stringIndex.objects);
          topDict._fdArray = fdArray;
          fdSelectOffset += start;
          topDict._fdSelect = parseCFFFDSelect(data, fdSelectOffset, font.numGlyphs, fdArray.length);
        }
        var privateDictOffset = start + topDict.private[1];
        var privateDict = parseCFFPrivateDict(data, privateDictOffset, topDict.private[0], stringIndex.objects);
        font.defaultWidthX = privateDict.defaultWidthX;
        font.nominalWidthX = privateDict.nominalWidthX;
        if (privateDict.subrs !== 0) {
          var subrOffset = privateDictOffset + privateDict.subrs;
          var subrIndex = parseCFFIndex(data, subrOffset);
          font.subrs = subrIndex.objects;
          font.subrsBias = calcCFFSubroutineBias(font.subrs);
        } else {
          font.subrs = [];
          font.subrsBias = 0;
        }
        var charStringsIndex;
        if (opt.lowMemory) {
          charStringsIndex = parseCFFIndexLowMemory(data, start + topDict.charStrings);
          font.nGlyphs = charStringsIndex.offsets.length;
        } else {
          charStringsIndex = parseCFFIndex(data, start + topDict.charStrings);
          font.nGlyphs = charStringsIndex.objects.length;
        }
        var charset = parseCFFCharset(data, start + topDict.charset, font.nGlyphs, stringIndex.objects);
        if (topDict.encoding === 0) {
          font.cffEncoding = new CffEncoding(cffStandardEncoding, charset);
        } else if (topDict.encoding === 1) {
          font.cffEncoding = new CffEncoding(cffExpertEncoding, charset);
        } else {
          font.cffEncoding = parseCFFEncoding(data, start + topDict.encoding, charset);
        }
        font.encoding = font.encoding || font.cffEncoding;
        font.glyphs = new glyphset.GlyphSet(font);
        if (opt.lowMemory) {
          font._push = function(i2) {
            var charString2 = getCffIndexObject(i2, charStringsIndex.offsets, data, start + topDict.charStrings);
            font.glyphs.push(i2, glyphset.cffGlyphLoader(font, i2, parseCFFCharstring, charString2));
          };
        } else {
          for (var i = 0; i < font.nGlyphs; i += 1) {
            var charString = charStringsIndex.objects[i];
            font.glyphs.push(i, glyphset.cffGlyphLoader(font, i, parseCFFCharstring, charString));
          }
        }
      }
      function encodeString2(s, strings) {
        var sid;
        var i = cffStandardStrings.indexOf(s);
        if (i >= 0) {
          sid = i;
        }
        i = strings.indexOf(s);
        if (i >= 0) {
          sid = i + cffStandardStrings.length;
        } else {
          sid = cffStandardStrings.length + strings.length;
          strings.push(s);
        }
        return sid;
      }
      function makeHeader() {
        return new table2.Record("Header", [
          { name: "major", type: "Card8", value: 1 },
          { name: "minor", type: "Card8", value: 0 },
          { name: "hdrSize", type: "Card8", value: 4 },
          { name: "major", type: "Card8", value: 1 }
        ]);
      }
      function makeNameIndex(fontNames) {
        var t = new table2.Record("Name INDEX", [
          { name: "names", type: "INDEX", value: [] }
        ]);
        t.names = [];
        for (var i = 0; i < fontNames.length; i += 1) {
          t.names.push({ name: "name_" + i, type: "NAME", value: fontNames[i] });
        }
        return t;
      }
      function makeDict(meta2, attrs, strings) {
        var m = {};
        for (var i = 0; i < meta2.length; i += 1) {
          var entry = meta2[i];
          var value = attrs[entry.name];
          if (value !== void 0 && !equals(value, entry.value)) {
            if (entry.type === "SID") {
              value = encodeString2(value, strings);
            }
            m[entry.op] = { name: entry.name, type: entry.type, value };
          }
        }
        return m;
      }
      function makeTopDict(attrs, strings) {
        var t = new table2.Record("Top DICT", [
          { name: "dict", type: "DICT", value: {} }
        ]);
        t.dict = makeDict(TOP_DICT_META, attrs, strings);
        return t;
      }
      function makeTopDictIndex(topDict) {
        var t = new table2.Record("Top DICT INDEX", [
          { name: "topDicts", type: "INDEX", value: [] }
        ]);
        t.topDicts = [{ name: "topDict_0", type: "TABLE", value: topDict }];
        return t;
      }
      function makeStringIndex(strings) {
        var t = new table2.Record("String INDEX", [
          { name: "strings", type: "INDEX", value: [] }
        ]);
        t.strings = [];
        for (var i = 0; i < strings.length; i += 1) {
          t.strings.push({ name: "string_" + i, type: "STRING", value: strings[i] });
        }
        return t;
      }
      function makeGlobalSubrIndex() {
        return new table2.Record("Global Subr INDEX", [
          { name: "subrs", type: "INDEX", value: [] }
        ]);
      }
      function makeCharsets(glyphNames, strings) {
        var t = new table2.Record("Charsets", [
          { name: "format", type: "Card8", value: 0 }
        ]);
        for (var i = 0; i < glyphNames.length; i += 1) {
          var glyphName = glyphNames[i];
          var glyphSID = encodeString2(glyphName, strings);
          t.fields.push({ name: "glyph_" + i, type: "SID", value: glyphSID });
        }
        return t;
      }
      function glyphToOps(glyph) {
        var ops = [];
        var path = glyph.path;
        ops.push({ name: "width", type: "NUMBER", value: glyph.advanceWidth });
        var x = 0;
        var y = 0;
        for (var i = 0; i < path.commands.length; i += 1) {
          var dx = void 0;
          var dy = void 0;
          var cmd = path.commands[i];
          if (cmd.type === "Q") {
            var _13 = 1 / 3;
            var _23 = 2 / 3;
            cmd = {
              type: "C",
              x: cmd.x,
              y: cmd.y,
              x1: Math.round(_13 * x + _23 * cmd.x1),
              y1: Math.round(_13 * y + _23 * cmd.y1),
              x2: Math.round(_13 * cmd.x + _23 * cmd.x1),
              y2: Math.round(_13 * cmd.y + _23 * cmd.y1)
            };
          }
          if (cmd.type === "M") {
            dx = Math.round(cmd.x - x);
            dy = Math.round(cmd.y - y);
            ops.push({ name: "dx", type: "NUMBER", value: dx });
            ops.push({ name: "dy", type: "NUMBER", value: dy });
            ops.push({ name: "rmoveto", type: "OP", value: 21 });
            x = Math.round(cmd.x);
            y = Math.round(cmd.y);
          } else if (cmd.type === "L") {
            dx = Math.round(cmd.x - x);
            dy = Math.round(cmd.y - y);
            ops.push({ name: "dx", type: "NUMBER", value: dx });
            ops.push({ name: "dy", type: "NUMBER", value: dy });
            ops.push({ name: "rlineto", type: "OP", value: 5 });
            x = Math.round(cmd.x);
            y = Math.round(cmd.y);
          } else if (cmd.type === "C") {
            var dx1 = Math.round(cmd.x1 - x);
            var dy1 = Math.round(cmd.y1 - y);
            var dx2 = Math.round(cmd.x2 - cmd.x1);
            var dy2 = Math.round(cmd.y2 - cmd.y1);
            dx = Math.round(cmd.x - cmd.x2);
            dy = Math.round(cmd.y - cmd.y2);
            ops.push({ name: "dx1", type: "NUMBER", value: dx1 });
            ops.push({ name: "dy1", type: "NUMBER", value: dy1 });
            ops.push({ name: "dx2", type: "NUMBER", value: dx2 });
            ops.push({ name: "dy2", type: "NUMBER", value: dy2 });
            ops.push({ name: "dx", type: "NUMBER", value: dx });
            ops.push({ name: "dy", type: "NUMBER", value: dy });
            ops.push({ name: "rrcurveto", type: "OP", value: 8 });
            x = Math.round(cmd.x);
            y = Math.round(cmd.y);
          }
        }
        ops.push({ name: "endchar", type: "OP", value: 14 });
        return ops;
      }
      function makeCharStringsIndex(glyphs) {
        var t = new table2.Record("CharStrings INDEX", [
          { name: "charStrings", type: "INDEX", value: [] }
        ]);
        for (var i = 0; i < glyphs.length; i += 1) {
          var glyph = glyphs.get(i);
          var ops = glyphToOps(glyph);
          t.charStrings.push({ name: glyph.name, type: "CHARSTRING", value: ops });
        }
        return t;
      }
      function makePrivateDict(attrs, strings) {
        var t = new table2.Record("Private DICT", [
          { name: "dict", type: "DICT", value: {} }
        ]);
        t.dict = makeDict(PRIVATE_DICT_META, attrs, strings);
        return t;
      }
      function makeCFFTable(glyphs, options) {
        var t = new table2.Table("CFF ", [
          { name: "header", type: "RECORD" },
          { name: "nameIndex", type: "RECORD" },
          { name: "topDictIndex", type: "RECORD" },
          { name: "stringIndex", type: "RECORD" },
          { name: "globalSubrIndex", type: "RECORD" },
          { name: "charsets", type: "RECORD" },
          { name: "charStringsIndex", type: "RECORD" },
          { name: "privateDict", type: "RECORD" }
        ]);
        var fontScale = 1 / options.unitsPerEm;
        var attrs = {
          version: options.version,
          fullName: options.fullName,
          familyName: options.familyName,
          weight: options.weightName,
          fontBBox: options.fontBBox || [0, 0, 0, 0],
          fontMatrix: [fontScale, 0, 0, fontScale, 0, 0],
          charset: 999,
          encoding: 0,
          charStrings: 999,
          private: [0, 999]
        };
        var privateAttrs = {};
        var glyphNames = [];
        var glyph;
        for (var i = 1; i < glyphs.length; i += 1) {
          glyph = glyphs.get(i);
          glyphNames.push(glyph.name);
        }
        var strings = [];
        t.header = makeHeader();
        t.nameIndex = makeNameIndex([options.postScriptName]);
        var topDict = makeTopDict(attrs, strings);
        t.topDictIndex = makeTopDictIndex(topDict);
        t.globalSubrIndex = makeGlobalSubrIndex();
        t.charsets = makeCharsets(glyphNames, strings);
        t.charStringsIndex = makeCharStringsIndex(glyphs);
        t.privateDict = makePrivateDict(privateAttrs, strings);
        t.stringIndex = makeStringIndex(strings);
        var startOffset = t.header.sizeOf() + t.nameIndex.sizeOf() + t.topDictIndex.sizeOf() + t.stringIndex.sizeOf() + t.globalSubrIndex.sizeOf();
        attrs.charset = startOffset;
        attrs.encoding = 0;
        attrs.charStrings = attrs.charset + t.charsets.sizeOf();
        attrs.private[1] = attrs.charStrings + t.charStringsIndex.sizeOf();
        topDict = makeTopDict(attrs, strings);
        t.topDictIndex = makeTopDictIndex(topDict);
        return t;
      }
      var cff = { parse: parseCFFTable, make: makeCFFTable };
      function parseHeadTable(data, start) {
        var head2 = {};
        var p = new parse2.Parser(data, start);
        head2.version = p.parseVersion();
        head2.fontRevision = Math.round(p.parseFixed() * 1e3) / 1e3;
        head2.checkSumAdjustment = p.parseULong();
        head2.magicNumber = p.parseULong();
        check.argument(head2.magicNumber === 1594834165, "Font header has wrong magic number.");
        head2.flags = p.parseUShort();
        head2.unitsPerEm = p.parseUShort();
        head2.created = p.parseLongDateTime();
        head2.modified = p.parseLongDateTime();
        head2.xMin = p.parseShort();
        head2.yMin = p.parseShort();
        head2.xMax = p.parseShort();
        head2.yMax = p.parseShort();
        head2.macStyle = p.parseUShort();
        head2.lowestRecPPEM = p.parseUShort();
        head2.fontDirectionHint = p.parseShort();
        head2.indexToLocFormat = p.parseShort();
        head2.glyphDataFormat = p.parseShort();
        return head2;
      }
      function makeHeadTable(options) {
        var timestamp = Math.round((/* @__PURE__ */ new Date()).getTime() / 1e3) + 2082844800;
        var createdTimestamp = timestamp;
        if (options.createdTimestamp) {
          createdTimestamp = options.createdTimestamp + 2082844800;
        }
        return new table2.Table("head", [
          { name: "version", type: "FIXED", value: 65536 },
          { name: "fontRevision", type: "FIXED", value: 65536 },
          { name: "checkSumAdjustment", type: "ULONG", value: 0 },
          { name: "magicNumber", type: "ULONG", value: 1594834165 },
          { name: "flags", type: "USHORT", value: 0 },
          { name: "unitsPerEm", type: "USHORT", value: 1e3 },
          { name: "created", type: "LONGDATETIME", value: createdTimestamp },
          { name: "modified", type: "LONGDATETIME", value: timestamp },
          { name: "xMin", type: "SHORT", value: 0 },
          { name: "yMin", type: "SHORT", value: 0 },
          { name: "xMax", type: "SHORT", value: 0 },
          { name: "yMax", type: "SHORT", value: 0 },
          { name: "macStyle", type: "USHORT", value: 0 },
          { name: "lowestRecPPEM", type: "USHORT", value: 0 },
          { name: "fontDirectionHint", type: "SHORT", value: 2 },
          { name: "indexToLocFormat", type: "SHORT", value: 0 },
          { name: "glyphDataFormat", type: "SHORT", value: 0 }
        ], options);
      }
      var head = { parse: parseHeadTable, make: makeHeadTable };
      function parseHheaTable(data, start) {
        var hhea2 = {};
        var p = new parse2.Parser(data, start);
        hhea2.version = p.parseVersion();
        hhea2.ascender = p.parseShort();
        hhea2.descender = p.parseShort();
        hhea2.lineGap = p.parseShort();
        hhea2.advanceWidthMax = p.parseUShort();
        hhea2.minLeftSideBearing = p.parseShort();
        hhea2.minRightSideBearing = p.parseShort();
        hhea2.xMaxExtent = p.parseShort();
        hhea2.caretSlopeRise = p.parseShort();
        hhea2.caretSlopeRun = p.parseShort();
        hhea2.caretOffset = p.parseShort();
        p.relativeOffset += 8;
        hhea2.metricDataFormat = p.parseShort();
        hhea2.numberOfHMetrics = p.parseUShort();
        return hhea2;
      }
      function makeHheaTable(options) {
        return new table2.Table("hhea", [
          { name: "version", type: "FIXED", value: 65536 },
          { name: "ascender", type: "FWORD", value: 0 },
          { name: "descender", type: "FWORD", value: 0 },
          { name: "lineGap", type: "FWORD", value: 0 },
          { name: "advanceWidthMax", type: "UFWORD", value: 0 },
          { name: "minLeftSideBearing", type: "FWORD", value: 0 },
          { name: "minRightSideBearing", type: "FWORD", value: 0 },
          { name: "xMaxExtent", type: "FWORD", value: 0 },
          { name: "caretSlopeRise", type: "SHORT", value: 1 },
          { name: "caretSlopeRun", type: "SHORT", value: 0 },
          { name: "caretOffset", type: "SHORT", value: 0 },
          { name: "reserved1", type: "SHORT", value: 0 },
          { name: "reserved2", type: "SHORT", value: 0 },
          { name: "reserved3", type: "SHORT", value: 0 },
          { name: "reserved4", type: "SHORT", value: 0 },
          { name: "metricDataFormat", type: "SHORT", value: 0 },
          { name: "numberOfHMetrics", type: "USHORT", value: 0 }
        ], options);
      }
      var hhea = { parse: parseHheaTable, make: makeHheaTable };
      function parseHmtxTableAll(data, start, numMetrics, numGlyphs, glyphs) {
        var advanceWidth;
        var leftSideBearing;
        var p = new parse2.Parser(data, start);
        for (var i = 0; i < numGlyphs; i += 1) {
          if (i < numMetrics) {
            advanceWidth = p.parseUShort();
            leftSideBearing = p.parseShort();
          }
          var glyph = glyphs.get(i);
          glyph.advanceWidth = advanceWidth;
          glyph.leftSideBearing = leftSideBearing;
        }
      }
      function parseHmtxTableOnLowMemory(font, data, start, numMetrics, numGlyphs) {
        font._hmtxTableData = {};
        var advanceWidth;
        var leftSideBearing;
        var p = new parse2.Parser(data, start);
        for (var i = 0; i < numGlyphs; i += 1) {
          if (i < numMetrics) {
            advanceWidth = p.parseUShort();
            leftSideBearing = p.parseShort();
          }
          font._hmtxTableData[i] = {
            advanceWidth,
            leftSideBearing
          };
        }
      }
      function parseHmtxTable(font, data, start, numMetrics, numGlyphs, glyphs, opt) {
        if (opt.lowMemory) {
          parseHmtxTableOnLowMemory(font, data, start, numMetrics, numGlyphs);
        } else {
          parseHmtxTableAll(data, start, numMetrics, numGlyphs, glyphs);
        }
      }
      function makeHmtxTable(glyphs) {
        var t = new table2.Table("hmtx", []);
        for (var i = 0; i < glyphs.length; i += 1) {
          var glyph = glyphs.get(i);
          var advanceWidth = glyph.advanceWidth || 0;
          var leftSideBearing = glyph.leftSideBearing || 0;
          t.fields.push({ name: "advanceWidth_" + i, type: "USHORT", value: advanceWidth });
          t.fields.push({ name: "leftSideBearing_" + i, type: "SHORT", value: leftSideBearing });
        }
        return t;
      }
      var hmtx = { parse: parseHmtxTable, make: makeHmtxTable };
      function makeLtagTable(tags) {
        var result = new table2.Table("ltag", [
          { name: "version", type: "ULONG", value: 1 },
          { name: "flags", type: "ULONG", value: 0 },
          { name: "numTags", type: "ULONG", value: tags.length }
        ]);
        var stringPool = "";
        var stringPoolOffset = 12 + tags.length * 4;
        for (var i = 0; i < tags.length; ++i) {
          var pos = stringPool.indexOf(tags[i]);
          if (pos < 0) {
            pos = stringPool.length;
            stringPool += tags[i];
          }
          result.fields.push({ name: "offset " + i, type: "USHORT", value: stringPoolOffset + pos });
          result.fields.push({ name: "length " + i, type: "USHORT", value: tags[i].length });
        }
        result.fields.push({ name: "stringPool", type: "CHARARRAY", value: stringPool });
        return result;
      }
      function parseLtagTable(data, start) {
        var p = new parse2.Parser(data, start);
        var tableVersion = p.parseULong();
        check.argument(tableVersion === 1, "Unsupported ltag table version.");
        p.skip("uLong", 1);
        var numTags = p.parseULong();
        var tags = [];
        for (var i = 0; i < numTags; i++) {
          var tag = "";
          var offset = start + p.parseUShort();
          var length = p.parseUShort();
          for (var j = offset; j < offset + length; ++j) {
            tag += String.fromCharCode(data.getInt8(j));
          }
          tags.push(tag);
        }
        return tags;
      }
      var ltag = { make: makeLtagTable, parse: parseLtagTable };
      function parseMaxpTable(data, start) {
        var maxp2 = {};
        var p = new parse2.Parser(data, start);
        maxp2.version = p.parseVersion();
        maxp2.numGlyphs = p.parseUShort();
        if (maxp2.version === 1) {
          maxp2.maxPoints = p.parseUShort();
          maxp2.maxContours = p.parseUShort();
          maxp2.maxCompositePoints = p.parseUShort();
          maxp2.maxCompositeContours = p.parseUShort();
          maxp2.maxZones = p.parseUShort();
          maxp2.maxTwilightPoints = p.parseUShort();
          maxp2.maxStorage = p.parseUShort();
          maxp2.maxFunctionDefs = p.parseUShort();
          maxp2.maxInstructionDefs = p.parseUShort();
          maxp2.maxStackElements = p.parseUShort();
          maxp2.maxSizeOfInstructions = p.parseUShort();
          maxp2.maxComponentElements = p.parseUShort();
          maxp2.maxComponentDepth = p.parseUShort();
        }
        return maxp2;
      }
      function makeMaxpTable(numGlyphs) {
        return new table2.Table("maxp", [
          { name: "version", type: "FIXED", value: 20480 },
          { name: "numGlyphs", type: "USHORT", value: numGlyphs }
        ]);
      }
      var maxp = { parse: parseMaxpTable, make: makeMaxpTable };
      var nameTableNames = [
        "copyright",
        // 0
        "fontFamily",
        // 1
        "fontSubfamily",
        // 2
        "uniqueID",
        // 3
        "fullName",
        // 4
        "version",
        // 5
        "postScriptName",
        // 6
        "trademark",
        // 7
        "manufacturer",
        // 8
        "designer",
        // 9
        "description",
        // 10
        "manufacturerURL",
        // 11
        "designerURL",
        // 12
        "license",
        // 13
        "licenseURL",
        // 14
        "reserved",
        // 15
        "preferredFamily",
        // 16
        "preferredSubfamily",
        // 17
        "compatibleFullName",
        // 18
        "sampleText",
        // 19
        "postScriptFindFontName",
        // 20
        "wwsFamily",
        // 21
        "wwsSubfamily"
        // 22
      ];
      var macLanguages = {
        0: "en",
        1: "fr",
        2: "de",
        3: "it",
        4: "nl",
        5: "sv",
        6: "es",
        7: "da",
        8: "pt",
        9: "no",
        10: "he",
        11: "ja",
        12: "ar",
        13: "fi",
        14: "el",
        15: "is",
        16: "mt",
        17: "tr",
        18: "hr",
        19: "zh-Hant",
        20: "ur",
        21: "hi",
        22: "th",
        23: "ko",
        24: "lt",
        25: "pl",
        26: "hu",
        27: "es",
        28: "lv",
        29: "se",
        30: "fo",
        31: "fa",
        32: "ru",
        33: "zh",
        34: "nl-BE",
        35: "ga",
        36: "sq",
        37: "ro",
        38: "cz",
        39: "sk",
        40: "si",
        41: "yi",
        42: "sr",
        43: "mk",
        44: "bg",
        45: "uk",
        46: "be",
        47: "uz",
        48: "kk",
        49: "az-Cyrl",
        50: "az-Arab",
        51: "hy",
        52: "ka",
        53: "mo",
        54: "ky",
        55: "tg",
        56: "tk",
        57: "mn-CN",
        58: "mn",
        59: "ps",
        60: "ks",
        61: "ku",
        62: "sd",
        63: "bo",
        64: "ne",
        65: "sa",
        66: "mr",
        67: "bn",
        68: "as",
        69: "gu",
        70: "pa",
        71: "or",
        72: "ml",
        73: "kn",
        74: "ta",
        75: "te",
        76: "si",
        77: "my",
        78: "km",
        79: "lo",
        80: "vi",
        81: "id",
        82: "tl",
        83: "ms",
        84: "ms-Arab",
        85: "am",
        86: "ti",
        87: "om",
        88: "so",
        89: "sw",
        90: "rw",
        91: "rn",
        92: "ny",
        93: "mg",
        94: "eo",
        128: "cy",
        129: "eu",
        130: "ca",
        131: "la",
        132: "qu",
        133: "gn",
        134: "ay",
        135: "tt",
        136: "ug",
        137: "dz",
        138: "jv",
        139: "su",
        140: "gl",
        141: "af",
        142: "br",
        143: "iu",
        144: "gd",
        145: "gv",
        146: "ga",
        147: "to",
        148: "el-polyton",
        149: "kl",
        150: "az",
        151: "nn"
      };
      var macLanguageToScript = {
        0: 0,
        // langEnglish → smRoman
        1: 0,
        // langFrench → smRoman
        2: 0,
        // langGerman → smRoman
        3: 0,
        // langItalian → smRoman
        4: 0,
        // langDutch → smRoman
        5: 0,
        // langSwedish → smRoman
        6: 0,
        // langSpanish → smRoman
        7: 0,
        // langDanish → smRoman
        8: 0,
        // langPortuguese → smRoman
        9: 0,
        // langNorwegian → smRoman
        10: 5,
        // langHebrew → smHebrew
        11: 1,
        // langJapanese → smJapanese
        12: 4,
        // langArabic → smArabic
        13: 0,
        // langFinnish → smRoman
        14: 6,
        // langGreek → smGreek
        15: 0,
        // langIcelandic → smRoman (modified)
        16: 0,
        // langMaltese → smRoman
        17: 0,
        // langTurkish → smRoman (modified)
        18: 0,
        // langCroatian → smRoman (modified)
        19: 2,
        // langTradChinese → smTradChinese
        20: 4,
        // langUrdu → smArabic
        21: 9,
        // langHindi → smDevanagari
        22: 21,
        // langThai → smThai
        23: 3,
        // langKorean → smKorean
        24: 29,
        // langLithuanian → smCentralEuroRoman
        25: 29,
        // langPolish → smCentralEuroRoman
        26: 29,
        // langHungarian → smCentralEuroRoman
        27: 29,
        // langEstonian → smCentralEuroRoman
        28: 29,
        // langLatvian → smCentralEuroRoman
        29: 0,
        // langSami → smRoman
        30: 0,
        // langFaroese → smRoman (modified)
        31: 4,
        // langFarsi → smArabic (modified)
        32: 7,
        // langRussian → smCyrillic
        33: 25,
        // langSimpChinese → smSimpChinese
        34: 0,
        // langFlemish → smRoman
        35: 0,
        // langIrishGaelic → smRoman (modified)
        36: 0,
        // langAlbanian → smRoman
        37: 0,
        // langRomanian → smRoman (modified)
        38: 29,
        // langCzech → smCentralEuroRoman
        39: 29,
        // langSlovak → smCentralEuroRoman
        40: 0,
        // langSlovenian → smRoman (modified)
        41: 5,
        // langYiddish → smHebrew
        42: 7,
        // langSerbian → smCyrillic
        43: 7,
        // langMacedonian → smCyrillic
        44: 7,
        // langBulgarian → smCyrillic
        45: 7,
        // langUkrainian → smCyrillic (modified)
        46: 7,
        // langByelorussian → smCyrillic
        47: 7,
        // langUzbek → smCyrillic
        48: 7,
        // langKazakh → smCyrillic
        49: 7,
        // langAzerbaijani → smCyrillic
        50: 4,
        // langAzerbaijanAr → smArabic
        51: 24,
        // langArmenian → smArmenian
        52: 23,
        // langGeorgian → smGeorgian
        53: 7,
        // langMoldavian → smCyrillic
        54: 7,
        // langKirghiz → smCyrillic
        55: 7,
        // langTajiki → smCyrillic
        56: 7,
        // langTurkmen → smCyrillic
        57: 27,
        // langMongolian → smMongolian
        58: 7,
        // langMongolianCyr → smCyrillic
        59: 4,
        // langPashto → smArabic
        60: 4,
        // langKurdish → smArabic
        61: 4,
        // langKashmiri → smArabic
        62: 4,
        // langSindhi → smArabic
        63: 26,
        // langTibetan → smTibetan
        64: 9,
        // langNepali → smDevanagari
        65: 9,
        // langSanskrit → smDevanagari
        66: 9,
        // langMarathi → smDevanagari
        67: 13,
        // langBengali → smBengali
        68: 13,
        // langAssamese → smBengali
        69: 11,
        // langGujarati → smGujarati
        70: 10,
        // langPunjabi → smGurmukhi
        71: 12,
        // langOriya → smOriya
        72: 17,
        // langMalayalam → smMalayalam
        73: 16,
        // langKannada → smKannada
        74: 14,
        // langTamil → smTamil
        75: 15,
        // langTelugu → smTelugu
        76: 18,
        // langSinhalese → smSinhalese
        77: 19,
        // langBurmese → smBurmese
        78: 20,
        // langKhmer → smKhmer
        79: 22,
        // langLao → smLao
        80: 30,
        // langVietnamese → smVietnamese
        81: 0,
        // langIndonesian → smRoman
        82: 0,
        // langTagalog → smRoman
        83: 0,
        // langMalayRoman → smRoman
        84: 4,
        // langMalayArabic → smArabic
        85: 28,
        // langAmharic → smEthiopic
        86: 28,
        // langTigrinya → smEthiopic
        87: 28,
        // langOromo → smEthiopic
        88: 0,
        // langSomali → smRoman
        89: 0,
        // langSwahili → smRoman
        90: 0,
        // langKinyarwanda → smRoman
        91: 0,
        // langRundi → smRoman
        92: 0,
        // langNyanja → smRoman
        93: 0,
        // langMalagasy → smRoman
        94: 0,
        // langEsperanto → smRoman
        128: 0,
        // langWelsh → smRoman (modified)
        129: 0,
        // langBasque → smRoman
        130: 0,
        // langCatalan → smRoman
        131: 0,
        // langLatin → smRoman
        132: 0,
        // langQuechua → smRoman
        133: 0,
        // langGuarani → smRoman
        134: 0,
        // langAymara → smRoman
        135: 7,
        // langTatar → smCyrillic
        136: 4,
        // langUighur → smArabic
        137: 26,
        // langDzongkha → smTibetan
        138: 0,
        // langJavaneseRom → smRoman
        139: 0,
        // langSundaneseRom → smRoman
        140: 0,
        // langGalician → smRoman
        141: 0,
        // langAfrikaans → smRoman
        142: 0,
        // langBreton → smRoman (modified)
        143: 28,
        // langInuktitut → smEthiopic (modified)
        144: 0,
        // langScottishGaelic → smRoman (modified)
        145: 0,
        // langManxGaelic → smRoman (modified)
        146: 0,
        // langIrishGaelicScript → smRoman (modified)
        147: 0,
        // langTongan → smRoman
        148: 6,
        // langGreekAncient → smRoman
        149: 0,
        // langGreenlandic → smRoman
        150: 0,
        // langAzerbaijanRoman → smRoman
        151: 0
        // langNynorsk → smRoman
      };
      var windowsLanguages = {
        1078: "af",
        1052: "sq",
        1156: "gsw",
        1118: "am",
        5121: "ar-DZ",
        15361: "ar-BH",
        3073: "ar",
        2049: "ar-IQ",
        11265: "ar-JO",
        13313: "ar-KW",
        12289: "ar-LB",
        4097: "ar-LY",
        6145: "ary",
        8193: "ar-OM",
        16385: "ar-QA",
        1025: "ar-SA",
        10241: "ar-SY",
        7169: "aeb",
        14337: "ar-AE",
        9217: "ar-YE",
        1067: "hy",
        1101: "as",
        2092: "az-Cyrl",
        1068: "az",
        1133: "ba",
        1069: "eu",
        1059: "be",
        2117: "bn",
        1093: "bn-IN",
        8218: "bs-Cyrl",
        5146: "bs",
        1150: "br",
        1026: "bg",
        1027: "ca",
        3076: "zh-HK",
        5124: "zh-MO",
        2052: "zh",
        4100: "zh-SG",
        1028: "zh-TW",
        1155: "co",
        1050: "hr",
        4122: "hr-BA",
        1029: "cs",
        1030: "da",
        1164: "prs",
        1125: "dv",
        2067: "nl-BE",
        1043: "nl",
        3081: "en-AU",
        10249: "en-BZ",
        4105: "en-CA",
        9225: "en-029",
        16393: "en-IN",
        6153: "en-IE",
        8201: "en-JM",
        17417: "en-MY",
        5129: "en-NZ",
        13321: "en-PH",
        18441: "en-SG",
        7177: "en-ZA",
        11273: "en-TT",
        2057: "en-GB",
        1033: "en",
        12297: "en-ZW",
        1061: "et",
        1080: "fo",
        1124: "fil",
        1035: "fi",
        2060: "fr-BE",
        3084: "fr-CA",
        1036: "fr",
        5132: "fr-LU",
        6156: "fr-MC",
        4108: "fr-CH",
        1122: "fy",
        1110: "gl",
        1079: "ka",
        3079: "de-AT",
        1031: "de",
        5127: "de-LI",
        4103: "de-LU",
        2055: "de-CH",
        1032: "el",
        1135: "kl",
        1095: "gu",
        1128: "ha",
        1037: "he",
        1081: "hi",
        1038: "hu",
        1039: "is",
        1136: "ig",
        1057: "id",
        1117: "iu",
        2141: "iu-Latn",
        2108: "ga",
        1076: "xh",
        1077: "zu",
        1040: "it",
        2064: "it-CH",
        1041: "ja",
        1099: "kn",
        1087: "kk",
        1107: "km",
        1158: "quc",
        1159: "rw",
        1089: "sw",
        1111: "kok",
        1042: "ko",
        1088: "ky",
        1108: "lo",
        1062: "lv",
        1063: "lt",
        2094: "dsb",
        1134: "lb",
        1071: "mk",
        2110: "ms-BN",
        1086: "ms",
        1100: "ml",
        1082: "mt",
        1153: "mi",
        1146: "arn",
        1102: "mr",
        1148: "moh",
        1104: "mn",
        2128: "mn-CN",
        1121: "ne",
        1044: "nb",
        2068: "nn",
        1154: "oc",
        1096: "or",
        1123: "ps",
        1045: "pl",
        1046: "pt",
        2070: "pt-PT",
        1094: "pa",
        1131: "qu-BO",
        2155: "qu-EC",
        3179: "qu",
        1048: "ro",
        1047: "rm",
        1049: "ru",
        9275: "smn",
        4155: "smj-NO",
        5179: "smj",
        3131: "se-FI",
        1083: "se",
        2107: "se-SE",
        8251: "sms",
        6203: "sma-NO",
        7227: "sms",
        1103: "sa",
        7194: "sr-Cyrl-BA",
        3098: "sr",
        6170: "sr-Latn-BA",
        2074: "sr-Latn",
        1132: "nso",
        1074: "tn",
        1115: "si",
        1051: "sk",
        1060: "sl",
        11274: "es-AR",
        16394: "es-BO",
        13322: "es-CL",
        9226: "es-CO",
        5130: "es-CR",
        7178: "es-DO",
        12298: "es-EC",
        17418: "es-SV",
        4106: "es-GT",
        18442: "es-HN",
        2058: "es-MX",
        19466: "es-NI",
        6154: "es-PA",
        15370: "es-PY",
        10250: "es-PE",
        20490: "es-PR",
        // Microsoft has defined two different language codes for
        // “Spanish with modern sorting” and “Spanish with traditional
        // sorting”. This makes sense for collation APIs, and it would be
        // possible to express this in BCP 47 language tags via Unicode
        // extensions (eg., es-u-co-trad is Spanish with traditional
        // sorting). However, for storing names in fonts, the distinction
        // does not make sense, so we give “es” in both cases.
        3082: "es",
        1034: "es",
        21514: "es-US",
        14346: "es-UY",
        8202: "es-VE",
        2077: "sv-FI",
        1053: "sv",
        1114: "syr",
        1064: "tg",
        2143: "tzm",
        1097: "ta",
        1092: "tt",
        1098: "te",
        1054: "th",
        1105: "bo",
        1055: "tr",
        1090: "tk",
        1152: "ug",
        1058: "uk",
        1070: "hsb",
        1056: "ur",
        2115: "uz-Cyrl",
        1091: "uz",
        1066: "vi",
        1106: "cy",
        1160: "wo",
        1157: "sah",
        1144: "ii",
        1130: "yo"
      };
      function getLanguageCode(platformID, languageID, ltag2) {
        switch (platformID) {
          case 0:
            if (languageID === 65535) {
              return "und";
            } else if (ltag2) {
              return ltag2[languageID];
            }
            break;
          case 1:
            return macLanguages[languageID];
          case 3:
            return windowsLanguages[languageID];
        }
        return void 0;
      }
      var utf16 = "utf-16";
      var macScriptEncodings = {
        0: "macintosh",
        // smRoman
        1: "x-mac-japanese",
        // smJapanese
        2: "x-mac-chinesetrad",
        // smTradChinese
        3: "x-mac-korean",
        // smKorean
        6: "x-mac-greek",
        // smGreek
        7: "x-mac-cyrillic",
        // smCyrillic
        9: "x-mac-devanagai",
        // smDevanagari
        10: "x-mac-gurmukhi",
        // smGurmukhi
        11: "x-mac-gujarati",
        // smGujarati
        12: "x-mac-oriya",
        // smOriya
        13: "x-mac-bengali",
        // smBengali
        14: "x-mac-tamil",
        // smTamil
        15: "x-mac-telugu",
        // smTelugu
        16: "x-mac-kannada",
        // smKannada
        17: "x-mac-malayalam",
        // smMalayalam
        18: "x-mac-sinhalese",
        // smSinhalese
        19: "x-mac-burmese",
        // smBurmese
        20: "x-mac-khmer",
        // smKhmer
        21: "x-mac-thai",
        // smThai
        22: "x-mac-lao",
        // smLao
        23: "x-mac-georgian",
        // smGeorgian
        24: "x-mac-armenian",
        // smArmenian
        25: "x-mac-chinesesimp",
        // smSimpChinese
        26: "x-mac-tibetan",
        // smTibetan
        27: "x-mac-mongolian",
        // smMongolian
        28: "x-mac-ethiopic",
        // smEthiopic
        29: "x-mac-ce",
        // smCentralEuroRoman
        30: "x-mac-vietnamese",
        // smVietnamese
        31: "x-mac-extarabic"
        // smExtArabic
      };
      var macLanguageEncodings = {
        15: "x-mac-icelandic",
        // langIcelandic
        17: "x-mac-turkish",
        // langTurkish
        18: "x-mac-croatian",
        // langCroatian
        24: "x-mac-ce",
        // langLithuanian
        25: "x-mac-ce",
        // langPolish
        26: "x-mac-ce",
        // langHungarian
        27: "x-mac-ce",
        // langEstonian
        28: "x-mac-ce",
        // langLatvian
        30: "x-mac-icelandic",
        // langFaroese
        37: "x-mac-romanian",
        // langRomanian
        38: "x-mac-ce",
        // langCzech
        39: "x-mac-ce",
        // langSlovak
        40: "x-mac-ce",
        // langSlovenian
        143: "x-mac-inuit",
        // langInuktitut
        146: "x-mac-gaelic"
        // langIrishGaelicScript
      };
      function getEncoding(platformID, encodingID, languageID) {
        switch (platformID) {
          case 0:
            return utf16;
          case 1:
            return macLanguageEncodings[languageID] || macScriptEncodings[encodingID];
          case 3:
            if (encodingID === 1 || encodingID === 10) {
              return utf16;
            }
            break;
        }
        return void 0;
      }
      function parseNameTable(data, start, ltag2) {
        var name = {};
        var p = new parse2.Parser(data, start);
        var format = p.parseUShort();
        var count = p.parseUShort();
        var stringOffset = p.offset + p.parseUShort();
        for (var i = 0; i < count; i++) {
          var platformID = p.parseUShort();
          var encodingID = p.parseUShort();
          var languageID = p.parseUShort();
          var nameID = p.parseUShort();
          var property = nameTableNames[nameID] || nameID;
          var byteLength = p.parseUShort();
          var offset = p.parseUShort();
          var language = getLanguageCode(platformID, languageID, ltag2);
          var encoding = getEncoding(platformID, encodingID, languageID);
          if (encoding !== void 0 && language !== void 0) {
            var text2 = void 0;
            if (encoding === utf16) {
              text2 = decode.UTF16(data, stringOffset + offset, byteLength);
            } else {
              text2 = decode.MACSTRING(data, stringOffset + offset, byteLength, encoding);
            }
            if (text2) {
              var translations = name[property];
              if (translations === void 0) {
                translations = name[property] = {};
              }
              translations[language] = text2;
            }
          }
        }
        var langTagCount = 0;
        if (format === 1) {
          langTagCount = p.parseUShort();
        }
        return name;
      }
      function reverseDict(dict) {
        var result = {};
        for (var key in dict) {
          result[dict[key]] = parseInt(key);
        }
        return result;
      }
      function makeNameRecord(platformID, encodingID, languageID, nameID, length, offset) {
        return new table2.Record("NameRecord", [
          { name: "platformID", type: "USHORT", value: platformID },
          { name: "encodingID", type: "USHORT", value: encodingID },
          { name: "languageID", type: "USHORT", value: languageID },
          { name: "nameID", type: "USHORT", value: nameID },
          { name: "length", type: "USHORT", value: length },
          { name: "offset", type: "USHORT", value: offset }
        ]);
      }
      function findSubArray(needle, haystack) {
        var needleLength = needle.length;
        var limit = haystack.length - needleLength + 1;
        loop:
          for (var pos = 0; pos < limit; pos++) {
            for (; pos < limit; pos++) {
              for (var k = 0; k < needleLength; k++) {
                if (haystack[pos + k] !== needle[k]) {
                  continue loop;
                }
              }
              return pos;
            }
          }
        return -1;
      }
      function addStringToPool(s, pool) {
        var offset = findSubArray(s, pool);
        if (offset < 0) {
          offset = pool.length;
          var i = 0;
          var len = s.length;
          for (; i < len; ++i) {
            pool.push(s[i]);
          }
        }
        return offset;
      }
      function makeNameTable(names, ltag2) {
        var nameID;
        var nameIDs = [];
        var namesWithNumericKeys = {};
        var nameTableIds = reverseDict(nameTableNames);
        for (var key in names) {
          var id = nameTableIds[key];
          if (id === void 0) {
            id = key;
          }
          nameID = parseInt(id);
          if (isNaN(nameID)) {
            throw new Error('Name table entry "' + key + '" does not exist, see nameTableNames for complete list.');
          }
          namesWithNumericKeys[nameID] = names[key];
          nameIDs.push(nameID);
        }
        var macLanguageIds = reverseDict(macLanguages);
        var windowsLanguageIds = reverseDict(windowsLanguages);
        var nameRecords = [];
        var stringPool = [];
        for (var i = 0; i < nameIDs.length; i++) {
          nameID = nameIDs[i];
          var translations = namesWithNumericKeys[nameID];
          for (var lang in translations) {
            var text2 = translations[lang];
            var macPlatform = 1;
            var macLanguage = macLanguageIds[lang];
            var macScript = macLanguageToScript[macLanguage];
            var macEncoding = getEncoding(macPlatform, macScript, macLanguage);
            var macName = encode.MACSTRING(text2, macEncoding);
            if (macName === void 0) {
              macPlatform = 0;
              macLanguage = ltag2.indexOf(lang);
              if (macLanguage < 0) {
                macLanguage = ltag2.length;
                ltag2.push(lang);
              }
              macScript = 4;
              macName = encode.UTF16(text2);
            }
            var macNameOffset = addStringToPool(macName, stringPool);
            nameRecords.push(makeNameRecord(
              macPlatform,
              macScript,
              macLanguage,
              nameID,
              macName.length,
              macNameOffset
            ));
            var winLanguage = windowsLanguageIds[lang];
            if (winLanguage !== void 0) {
              var winName = encode.UTF16(text2);
              var winNameOffset = addStringToPool(winName, stringPool);
              nameRecords.push(makeNameRecord(
                3,
                1,
                winLanguage,
                nameID,
                winName.length,
                winNameOffset
              ));
            }
          }
        }
        nameRecords.sort(function(a, b2) {
          return a.platformID - b2.platformID || a.encodingID - b2.encodingID || a.languageID - b2.languageID || a.nameID - b2.nameID;
        });
        var t = new table2.Table("name", [
          { name: "format", type: "USHORT", value: 0 },
          { name: "count", type: "USHORT", value: nameRecords.length },
          { name: "stringOffset", type: "USHORT", value: 6 + nameRecords.length * 12 }
        ]);
        for (var r = 0; r < nameRecords.length; r++) {
          t.fields.push({ name: "record_" + r, type: "RECORD", value: nameRecords[r] });
        }
        t.fields.push({ name: "strings", type: "LITERAL", value: stringPool });
        return t;
      }
      var _name = { parse: parseNameTable, make: makeNameTable };
      var unicodeRanges = [
        { begin: 0, end: 127 },
        // Basic Latin
        { begin: 128, end: 255 },
        // Latin-1 Supplement
        { begin: 256, end: 383 },
        // Latin Extended-A
        { begin: 384, end: 591 },
        // Latin Extended-B
        { begin: 592, end: 687 },
        // IPA Extensions
        { begin: 688, end: 767 },
        // Spacing Modifier Letters
        { begin: 768, end: 879 },
        // Combining Diacritical Marks
        { begin: 880, end: 1023 },
        // Greek and Coptic
        { begin: 11392, end: 11519 },
        // Coptic
        { begin: 1024, end: 1279 },
        // Cyrillic
        { begin: 1328, end: 1423 },
        // Armenian
        { begin: 1424, end: 1535 },
        // Hebrew
        { begin: 42240, end: 42559 },
        // Vai
        { begin: 1536, end: 1791 },
        // Arabic
        { begin: 1984, end: 2047 },
        // NKo
        { begin: 2304, end: 2431 },
        // Devanagari
        { begin: 2432, end: 2559 },
        // Bengali
        { begin: 2560, end: 2687 },
        // Gurmukhi
        { begin: 2688, end: 2815 },
        // Gujarati
        { begin: 2816, end: 2943 },
        // Oriya
        { begin: 2944, end: 3071 },
        // Tamil
        { begin: 3072, end: 3199 },
        // Telugu
        { begin: 3200, end: 3327 },
        // Kannada
        { begin: 3328, end: 3455 },
        // Malayalam
        { begin: 3584, end: 3711 },
        // Thai
        { begin: 3712, end: 3839 },
        // Lao
        { begin: 4256, end: 4351 },
        // Georgian
        { begin: 6912, end: 7039 },
        // Balinese
        { begin: 4352, end: 4607 },
        // Hangul Jamo
        { begin: 7680, end: 7935 },
        // Latin Extended Additional
        { begin: 7936, end: 8191 },
        // Greek Extended
        { begin: 8192, end: 8303 },
        // General Punctuation
        { begin: 8304, end: 8351 },
        // Superscripts And Subscripts
        { begin: 8352, end: 8399 },
        // Currency Symbol
        { begin: 8400, end: 8447 },
        // Combining Diacritical Marks For Symbols
        { begin: 8448, end: 8527 },
        // Letterlike Symbols
        { begin: 8528, end: 8591 },
        // Number Forms
        { begin: 8592, end: 8703 },
        // Arrows
        { begin: 8704, end: 8959 },
        // Mathematical Operators
        { begin: 8960, end: 9215 },
        // Miscellaneous Technical
        { begin: 9216, end: 9279 },
        // Control Pictures
        { begin: 9280, end: 9311 },
        // Optical Character Recognition
        { begin: 9312, end: 9471 },
        // Enclosed Alphanumerics
        { begin: 9472, end: 9599 },
        // Box Drawing
        { begin: 9600, end: 9631 },
        // Block Elements
        { begin: 9632, end: 9727 },
        // Geometric Shapes
        { begin: 9728, end: 9983 },
        // Miscellaneous Symbols
        { begin: 9984, end: 10175 },
        // Dingbats
        { begin: 12288, end: 12351 },
        // CJK Symbols And Punctuation
        { begin: 12352, end: 12447 },
        // Hiragana
        { begin: 12448, end: 12543 },
        // Katakana
        { begin: 12544, end: 12591 },
        // Bopomofo
        { begin: 12592, end: 12687 },
        // Hangul Compatibility Jamo
        { begin: 43072, end: 43135 },
        // Phags-pa
        { begin: 12800, end: 13055 },
        // Enclosed CJK Letters And Months
        { begin: 13056, end: 13311 },
        // CJK Compatibility
        { begin: 44032, end: 55215 },
        // Hangul Syllables
        { begin: 55296, end: 57343 },
        // Non-Plane 0 *
        { begin: 67840, end: 67871 },
        // Phoenicia
        { begin: 19968, end: 40959 },
        // CJK Unified Ideographs
        { begin: 57344, end: 63743 },
        // Private Use Area (plane 0)
        { begin: 12736, end: 12783 },
        // CJK Strokes
        { begin: 64256, end: 64335 },
        // Alphabetic Presentation Forms
        { begin: 64336, end: 65023 },
        // Arabic Presentation Forms-A
        { begin: 65056, end: 65071 },
        // Combining Half Marks
        { begin: 65040, end: 65055 },
        // Vertical Forms
        { begin: 65104, end: 65135 },
        // Small Form Variants
        { begin: 65136, end: 65279 },
        // Arabic Presentation Forms-B
        { begin: 65280, end: 65519 },
        // Halfwidth And Fullwidth Forms
        { begin: 65520, end: 65535 },
        // Specials
        { begin: 3840, end: 4095 },
        // Tibetan
        { begin: 1792, end: 1871 },
        // Syriac
        { begin: 1920, end: 1983 },
        // Thaana
        { begin: 3456, end: 3583 },
        // Sinhala
        { begin: 4096, end: 4255 },
        // Myanmar
        { begin: 4608, end: 4991 },
        // Ethiopic
        { begin: 5024, end: 5119 },
        // Cherokee
        { begin: 5120, end: 5759 },
        // Unified Canadian Aboriginal Syllabics
        { begin: 5760, end: 5791 },
        // Ogham
        { begin: 5792, end: 5887 },
        // Runic
        { begin: 6016, end: 6143 },
        // Khmer
        { begin: 6144, end: 6319 },
        // Mongolian
        { begin: 10240, end: 10495 },
        // Braille Patterns
        { begin: 40960, end: 42127 },
        // Yi Syllables
        { begin: 5888, end: 5919 },
        // Tagalog
        { begin: 66304, end: 66351 },
        // Old Italic
        { begin: 66352, end: 66383 },
        // Gothic
        { begin: 66560, end: 66639 },
        // Deseret
        { begin: 118784, end: 119039 },
        // Byzantine Musical Symbols
        { begin: 119808, end: 120831 },
        // Mathematical Alphanumeric Symbols
        { begin: 1044480, end: 1048573 },
        // Private Use (plane 15)
        { begin: 65024, end: 65039 },
        // Variation Selectors
        { begin: 917504, end: 917631 },
        // Tags
        { begin: 6400, end: 6479 },
        // Limbu
        { begin: 6480, end: 6527 },
        // Tai Le
        { begin: 6528, end: 6623 },
        // New Tai Lue
        { begin: 6656, end: 6687 },
        // Buginese
        { begin: 11264, end: 11359 },
        // Glagolitic
        { begin: 11568, end: 11647 },
        // Tifinagh
        { begin: 19904, end: 19967 },
        // Yijing Hexagram Symbols
        { begin: 43008, end: 43055 },
        // Syloti Nagri
        { begin: 65536, end: 65663 },
        // Linear B Syllabary
        { begin: 65856, end: 65935 },
        // Ancient Greek Numbers
        { begin: 66432, end: 66463 },
        // Ugaritic
        { begin: 66464, end: 66527 },
        // Old Persian
        { begin: 66640, end: 66687 },
        // Shavian
        { begin: 66688, end: 66735 },
        // Osmanya
        { begin: 67584, end: 67647 },
        // Cypriot Syllabary
        { begin: 68096, end: 68191 },
        // Kharoshthi
        { begin: 119552, end: 119647 },
        // Tai Xuan Jing Symbols
        { begin: 73728, end: 74751 },
        // Cuneiform
        { begin: 119648, end: 119679 },
        // Counting Rod Numerals
        { begin: 7040, end: 7103 },
        // Sundanese
        { begin: 7168, end: 7247 },
        // Lepcha
        { begin: 7248, end: 7295 },
        // Ol Chiki
        { begin: 43136, end: 43231 },
        // Saurashtra
        { begin: 43264, end: 43311 },
        // Kayah Li
        { begin: 43312, end: 43359 },
        // Rejang
        { begin: 43520, end: 43615 },
        // Cham
        { begin: 65936, end: 65999 },
        // Ancient Symbols
        { begin: 66e3, end: 66047 },
        // Phaistos Disc
        { begin: 66208, end: 66271 },
        // Carian
        { begin: 127024, end: 127135 }
        // Domino Tiles
      ];
      function getUnicodeRange(unicode) {
        for (var i = 0; i < unicodeRanges.length; i += 1) {
          var range = unicodeRanges[i];
          if (unicode >= range.begin && unicode < range.end) {
            return i;
          }
        }
        return -1;
      }
      function parseOS2Table(data, start) {
        var os22 = {};
        var p = new parse2.Parser(data, start);
        os22.version = p.parseUShort();
        os22.xAvgCharWidth = p.parseShort();
        os22.usWeightClass = p.parseUShort();
        os22.usWidthClass = p.parseUShort();
        os22.fsType = p.parseUShort();
        os22.ySubscriptXSize = p.parseShort();
        os22.ySubscriptYSize = p.parseShort();
        os22.ySubscriptXOffset = p.parseShort();
        os22.ySubscriptYOffset = p.parseShort();
        os22.ySuperscriptXSize = p.parseShort();
        os22.ySuperscriptYSize = p.parseShort();
        os22.ySuperscriptXOffset = p.parseShort();
        os22.ySuperscriptYOffset = p.parseShort();
        os22.yStrikeoutSize = p.parseShort();
        os22.yStrikeoutPosition = p.parseShort();
        os22.sFamilyClass = p.parseShort();
        os22.panose = [];
        for (var i = 0; i < 10; i++) {
          os22.panose[i] = p.parseByte();
        }
        os22.ulUnicodeRange1 = p.parseULong();
        os22.ulUnicodeRange2 = p.parseULong();
        os22.ulUnicodeRange3 = p.parseULong();
        os22.ulUnicodeRange4 = p.parseULong();
        os22.achVendID = String.fromCharCode(p.parseByte(), p.parseByte(), p.parseByte(), p.parseByte());
        os22.fsSelection = p.parseUShort();
        os22.usFirstCharIndex = p.parseUShort();
        os22.usLastCharIndex = p.parseUShort();
        os22.sTypoAscender = p.parseShort();
        os22.sTypoDescender = p.parseShort();
        os22.sTypoLineGap = p.parseShort();
        os22.usWinAscent = p.parseUShort();
        os22.usWinDescent = p.parseUShort();
        if (os22.version >= 1) {
          os22.ulCodePageRange1 = p.parseULong();
          os22.ulCodePageRange2 = p.parseULong();
        }
        if (os22.version >= 2) {
          os22.sxHeight = p.parseShort();
          os22.sCapHeight = p.parseShort();
          os22.usDefaultChar = p.parseUShort();
          os22.usBreakChar = p.parseUShort();
          os22.usMaxContent = p.parseUShort();
        }
        return os22;
      }
      function makeOS2Table(options) {
        return new table2.Table("OS/2", [
          { name: "version", type: "USHORT", value: 3 },
          { name: "xAvgCharWidth", type: "SHORT", value: 0 },
          { name: "usWeightClass", type: "USHORT", value: 0 },
          { name: "usWidthClass", type: "USHORT", value: 0 },
          { name: "fsType", type: "USHORT", value: 0 },
          { name: "ySubscriptXSize", type: "SHORT", value: 650 },
          { name: "ySubscriptYSize", type: "SHORT", value: 699 },
          { name: "ySubscriptXOffset", type: "SHORT", value: 0 },
          { name: "ySubscriptYOffset", type: "SHORT", value: 140 },
          { name: "ySuperscriptXSize", type: "SHORT", value: 650 },
          { name: "ySuperscriptYSize", type: "SHORT", value: 699 },
          { name: "ySuperscriptXOffset", type: "SHORT", value: 0 },
          { name: "ySuperscriptYOffset", type: "SHORT", value: 479 },
          { name: "yStrikeoutSize", type: "SHORT", value: 49 },
          { name: "yStrikeoutPosition", type: "SHORT", value: 258 },
          { name: "sFamilyClass", type: "SHORT", value: 0 },
          { name: "bFamilyType", type: "BYTE", value: 0 },
          { name: "bSerifStyle", type: "BYTE", value: 0 },
          { name: "bWeight", type: "BYTE", value: 0 },
          { name: "bProportion", type: "BYTE", value: 0 },
          { name: "bContrast", type: "BYTE", value: 0 },
          { name: "bStrokeVariation", type: "BYTE", value: 0 },
          { name: "bArmStyle", type: "BYTE", value: 0 },
          { name: "bLetterform", type: "BYTE", value: 0 },
          { name: "bMidline", type: "BYTE", value: 0 },
          { name: "bXHeight", type: "BYTE", value: 0 },
          { name: "ulUnicodeRange1", type: "ULONG", value: 0 },
          { name: "ulUnicodeRange2", type: "ULONG", value: 0 },
          { name: "ulUnicodeRange3", type: "ULONG", value: 0 },
          { name: "ulUnicodeRange4", type: "ULONG", value: 0 },
          { name: "achVendID", type: "CHARARRAY", value: "XXXX" },
          { name: "fsSelection", type: "USHORT", value: 0 },
          { name: "usFirstCharIndex", type: "USHORT", value: 0 },
          { name: "usLastCharIndex", type: "USHORT", value: 0 },
          { name: "sTypoAscender", type: "SHORT", value: 0 },
          { name: "sTypoDescender", type: "SHORT", value: 0 },
          { name: "sTypoLineGap", type: "SHORT", value: 0 },
          { name: "usWinAscent", type: "USHORT", value: 0 },
          { name: "usWinDescent", type: "USHORT", value: 0 },
          { name: "ulCodePageRange1", type: "ULONG", value: 0 },
          { name: "ulCodePageRange2", type: "ULONG", value: 0 },
          { name: "sxHeight", type: "SHORT", value: 0 },
          { name: "sCapHeight", type: "SHORT", value: 0 },
          { name: "usDefaultChar", type: "USHORT", value: 0 },
          { name: "usBreakChar", type: "USHORT", value: 0 },
          { name: "usMaxContext", type: "USHORT", value: 0 }
        ], options);
      }
      var os2 = { parse: parseOS2Table, make: makeOS2Table, unicodeRanges, getUnicodeRange };
      function parsePostTable(data, start) {
        var post2 = {};
        var p = new parse2.Parser(data, start);
        post2.version = p.parseVersion();
        post2.italicAngle = p.parseFixed();
        post2.underlinePosition = p.parseShort();
        post2.underlineThickness = p.parseShort();
        post2.isFixedPitch = p.parseULong();
        post2.minMemType42 = p.parseULong();
        post2.maxMemType42 = p.parseULong();
        post2.minMemType1 = p.parseULong();
        post2.maxMemType1 = p.parseULong();
        switch (post2.version) {
          case 1:
            post2.names = standardNames.slice();
            break;
          case 2:
            post2.numberOfGlyphs = p.parseUShort();
            post2.glyphNameIndex = new Array(post2.numberOfGlyphs);
            for (var i = 0; i < post2.numberOfGlyphs; i++) {
              post2.glyphNameIndex[i] = p.parseUShort();
            }
            post2.names = [];
            for (var i$1 = 0; i$1 < post2.numberOfGlyphs; i$1++) {
              if (post2.glyphNameIndex[i$1] >= standardNames.length) {
                var nameLength = p.parseChar();
                post2.names.push(p.parseString(nameLength));
              }
            }
            break;
          case 2.5:
            post2.numberOfGlyphs = p.parseUShort();
            post2.offset = new Array(post2.numberOfGlyphs);
            for (var i$2 = 0; i$2 < post2.numberOfGlyphs; i$2++) {
              post2.offset[i$2] = p.parseChar();
            }
            break;
        }
        return post2;
      }
      function makePostTable() {
        return new table2.Table("post", [
          { name: "version", type: "FIXED", value: 196608 },
          { name: "italicAngle", type: "FIXED", value: 0 },
          { name: "underlinePosition", type: "FWORD", value: 0 },
          { name: "underlineThickness", type: "FWORD", value: 0 },
          { name: "isFixedPitch", type: "ULONG", value: 0 },
          { name: "minMemType42", type: "ULONG", value: 0 },
          { name: "maxMemType42", type: "ULONG", value: 0 },
          { name: "minMemType1", type: "ULONG", value: 0 },
          { name: "maxMemType1", type: "ULONG", value: 0 }
        ]);
      }
      var post = { parse: parsePostTable, make: makePostTable };
      var subtableParsers = new Array(9);
      subtableParsers[1] = function parseLookup1() {
        var start = this.offset + this.relativeOffset;
        var substFormat = this.parseUShort();
        if (substFormat === 1) {
          return {
            substFormat: 1,
            coverage: this.parsePointer(Parser.coverage),
            deltaGlyphId: this.parseUShort()
          };
        } else if (substFormat === 2) {
          return {
            substFormat: 2,
            coverage: this.parsePointer(Parser.coverage),
            substitute: this.parseOffset16List()
          };
        }
        check.assert(false, "0x" + start.toString(16) + ": lookup type 1 format must be 1 or 2.");
      };
      subtableParsers[2] = function parseLookup2() {
        var substFormat = this.parseUShort();
        check.argument(substFormat === 1, "GSUB Multiple Substitution Subtable identifier-format must be 1");
        return {
          substFormat,
          coverage: this.parsePointer(Parser.coverage),
          sequences: this.parseListOfLists()
        };
      };
      subtableParsers[3] = function parseLookup3() {
        var substFormat = this.parseUShort();
        check.argument(substFormat === 1, "GSUB Alternate Substitution Subtable identifier-format must be 1");
        return {
          substFormat,
          coverage: this.parsePointer(Parser.coverage),
          alternateSets: this.parseListOfLists()
        };
      };
      subtableParsers[4] = function parseLookup4() {
        var substFormat = this.parseUShort();
        check.argument(substFormat === 1, "GSUB ligature table identifier-format must be 1");
        return {
          substFormat,
          coverage: this.parsePointer(Parser.coverage),
          ligatureSets: this.parseListOfLists(function() {
            return {
              ligGlyph: this.parseUShort(),
              components: this.parseUShortList(this.parseUShort() - 1)
            };
          })
        };
      };
      var lookupRecordDesc = {
        sequenceIndex: Parser.uShort,
        lookupListIndex: Parser.uShort
      };
      subtableParsers[5] = function parseLookup5() {
        var start = this.offset + this.relativeOffset;
        var substFormat = this.parseUShort();
        if (substFormat === 1) {
          return {
            substFormat,
            coverage: this.parsePointer(Parser.coverage),
            ruleSets: this.parseListOfLists(function() {
              var glyphCount2 = this.parseUShort();
              var substCount2 = this.parseUShort();
              return {
                input: this.parseUShortList(glyphCount2 - 1),
                lookupRecords: this.parseRecordList(substCount2, lookupRecordDesc)
              };
            })
          };
        } else if (substFormat === 2) {
          return {
            substFormat,
            coverage: this.parsePointer(Parser.coverage),
            classDef: this.parsePointer(Parser.classDef),
            classSets: this.parseListOfLists(function() {
              var glyphCount2 = this.parseUShort();
              var substCount2 = this.parseUShort();
              return {
                classes: this.parseUShortList(glyphCount2 - 1),
                lookupRecords: this.parseRecordList(substCount2, lookupRecordDesc)
              };
            })
          };
        } else if (substFormat === 3) {
          var glyphCount = this.parseUShort();
          var substCount = this.parseUShort();
          return {
            substFormat,
            coverages: this.parseList(glyphCount, Parser.pointer(Parser.coverage)),
            lookupRecords: this.parseRecordList(substCount, lookupRecordDesc)
          };
        }
        check.assert(false, "0x" + start.toString(16) + ": lookup type 5 format must be 1, 2 or 3.");
      };
      subtableParsers[6] = function parseLookup6() {
        var start = this.offset + this.relativeOffset;
        var substFormat = this.parseUShort();
        if (substFormat === 1) {
          return {
            substFormat: 1,
            coverage: this.parsePointer(Parser.coverage),
            chainRuleSets: this.parseListOfLists(function() {
              return {
                backtrack: this.parseUShortList(),
                input: this.parseUShortList(this.parseShort() - 1),
                lookahead: this.parseUShortList(),
                lookupRecords: this.parseRecordList(lookupRecordDesc)
              };
            })
          };
        } else if (substFormat === 2) {
          return {
            substFormat: 2,
            coverage: this.parsePointer(Parser.coverage),
            backtrackClassDef: this.parsePointer(Parser.classDef),
            inputClassDef: this.parsePointer(Parser.classDef),
            lookaheadClassDef: this.parsePointer(Parser.classDef),
            chainClassSet: this.parseListOfLists(function() {
              return {
                backtrack: this.parseUShortList(),
                input: this.parseUShortList(this.parseShort() - 1),
                lookahead: this.parseUShortList(),
                lookupRecords: this.parseRecordList(lookupRecordDesc)
              };
            })
          };
        } else if (substFormat === 3) {
          return {
            substFormat: 3,
            backtrackCoverage: this.parseList(Parser.pointer(Parser.coverage)),
            inputCoverage: this.parseList(Parser.pointer(Parser.coverage)),
            lookaheadCoverage: this.parseList(Parser.pointer(Parser.coverage)),
            lookupRecords: this.parseRecordList(lookupRecordDesc)
          };
        }
        check.assert(false, "0x" + start.toString(16) + ": lookup type 6 format must be 1, 2 or 3.");
      };
      subtableParsers[7] = function parseLookup7() {
        var substFormat = this.parseUShort();
        check.argument(substFormat === 1, "GSUB Extension Substitution subtable identifier-format must be 1");
        var extensionLookupType = this.parseUShort();
        var extensionParser = new Parser(this.data, this.offset + this.parseULong());
        return {
          substFormat: 1,
          lookupType: extensionLookupType,
          extension: subtableParsers[extensionLookupType].call(extensionParser)
        };
      };
      subtableParsers[8] = function parseLookup8() {
        var substFormat = this.parseUShort();
        check.argument(substFormat === 1, "GSUB Reverse Chaining Contextual Single Substitution Subtable identifier-format must be 1");
        return {
          substFormat,
          coverage: this.parsePointer(Parser.coverage),
          backtrackCoverage: this.parseList(Parser.pointer(Parser.coverage)),
          lookaheadCoverage: this.parseList(Parser.pointer(Parser.coverage)),
          substitutes: this.parseUShortList()
        };
      };
      function parseGsubTable(data, start) {
        start = start || 0;
        var p = new Parser(data, start);
        var tableVersion = p.parseVersion(1);
        check.argument(tableVersion === 1 || tableVersion === 1.1, "Unsupported GSUB table version.");
        if (tableVersion === 1) {
          return {
            version: tableVersion,
            scripts: p.parseScriptList(),
            features: p.parseFeatureList(),
            lookups: p.parseLookupList(subtableParsers)
          };
        } else {
          return {
            version: tableVersion,
            scripts: p.parseScriptList(),
            features: p.parseFeatureList(),
            lookups: p.parseLookupList(subtableParsers),
            variations: p.parseFeatureVariationsList()
          };
        }
      }
      var subtableMakers = new Array(9);
      subtableMakers[1] = function makeLookup1(subtable) {
        if (subtable.substFormat === 1) {
          return new table2.Table("substitutionTable", [
            { name: "substFormat", type: "USHORT", value: 1 },
            { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) },
            { name: "deltaGlyphID", type: "USHORT", value: subtable.deltaGlyphId }
          ]);
        } else {
          return new table2.Table("substitutionTable", [
            { name: "substFormat", type: "USHORT", value: 2 },
            { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) }
          ].concat(table2.ushortList("substitute", subtable.substitute)));
        }
      };
      subtableMakers[2] = function makeLookup2(subtable) {
        check.assert(subtable.substFormat === 1, "Lookup type 2 substFormat must be 1.");
        return new table2.Table("substitutionTable", [
          { name: "substFormat", type: "USHORT", value: 1 },
          { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) }
        ].concat(table2.tableList("seqSet", subtable.sequences, function(sequenceSet) {
          return new table2.Table("sequenceSetTable", table2.ushortList("sequence", sequenceSet));
        })));
      };
      subtableMakers[3] = function makeLookup3(subtable) {
        check.assert(subtable.substFormat === 1, "Lookup type 3 substFormat must be 1.");
        return new table2.Table("substitutionTable", [
          { name: "substFormat", type: "USHORT", value: 1 },
          { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) }
        ].concat(table2.tableList("altSet", subtable.alternateSets, function(alternateSet) {
          return new table2.Table("alternateSetTable", table2.ushortList("alternate", alternateSet));
        })));
      };
      subtableMakers[4] = function makeLookup4(subtable) {
        check.assert(subtable.substFormat === 1, "Lookup type 4 substFormat must be 1.");
        return new table2.Table("substitutionTable", [
          { name: "substFormat", type: "USHORT", value: 1 },
          { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) }
        ].concat(table2.tableList("ligSet", subtable.ligatureSets, function(ligatureSet) {
          return new table2.Table("ligatureSetTable", table2.tableList("ligature", ligatureSet, function(ligature) {
            return new table2.Table(
              "ligatureTable",
              [{ name: "ligGlyph", type: "USHORT", value: ligature.ligGlyph }].concat(table2.ushortList("component", ligature.components, ligature.components.length + 1))
            );
          }));
        })));
      };
      subtableMakers[6] = function makeLookup6(subtable) {
        if (subtable.substFormat === 1) {
          var returnTable = new table2.Table("chainContextTable", [
            { name: "substFormat", type: "USHORT", value: subtable.substFormat },
            { name: "coverage", type: "TABLE", value: new table2.Coverage(subtable.coverage) }
          ].concat(table2.tableList("chainRuleSet", subtable.chainRuleSets, function(chainRuleSet) {
            return new table2.Table("chainRuleSetTable", table2.tableList("chainRule", chainRuleSet, function(chainRule) {
              var tableData2 = table2.ushortList("backtrackGlyph", chainRule.backtrack, chainRule.backtrack.length).concat(table2.ushortList("inputGlyph", chainRule.input, chainRule.input.length + 1)).concat(table2.ushortList("lookaheadGlyph", chainRule.lookahead, chainRule.lookahead.length)).concat(table2.ushortList("substitution", [], chainRule.lookupRecords.length));
              chainRule.lookupRecords.forEach(function(record, i) {
                tableData2 = tableData2.concat({ name: "sequenceIndex" + i, type: "USHORT", value: record.sequenceIndex }).concat({ name: "lookupListIndex" + i, type: "USHORT", value: record.lookupListIndex });
              });
              return new table2.Table("chainRuleTable", tableData2);
            }));
          })));
          return returnTable;
        } else if (subtable.substFormat === 2) {
          check.assert(false, "lookup type 6 format 2 is not yet supported.");
        } else if (subtable.substFormat === 3) {
          var tableData = [
            { name: "substFormat", type: "USHORT", value: subtable.substFormat }
          ];
          tableData.push({ name: "backtrackGlyphCount", type: "USHORT", value: subtable.backtrackCoverage.length });
          subtable.backtrackCoverage.forEach(function(coverage, i) {
            tableData.push({ name: "backtrackCoverage" + i, type: "TABLE", value: new table2.Coverage(coverage) });
          });
          tableData.push({ name: "inputGlyphCount", type: "USHORT", value: subtable.inputCoverage.length });
          subtable.inputCoverage.forEach(function(coverage, i) {
            tableData.push({ name: "inputCoverage" + i, type: "TABLE", value: new table2.Coverage(coverage) });
          });
          tableData.push({ name: "lookaheadGlyphCount", type: "USHORT", value: subtable.lookaheadCoverage.length });
          subtable.lookaheadCoverage.forEach(function(coverage, i) {
            tableData.push({ name: "lookaheadCoverage" + i, type: "TABLE", value: new table2.Coverage(coverage) });
          });
          tableData.push({ name: "substitutionCount", type: "USHORT", value: subtable.lookupRecords.length });
          subtable.lookupRecords.forEach(function(record, i) {
            tableData = tableData.concat({ name: "sequenceIndex" + i, type: "USHORT", value: record.sequenceIndex }).concat({ name: "lookupListIndex" + i, type: "USHORT", value: record.lookupListIndex });
          });
          var returnTable$1 = new table2.Table("chainContextTable", tableData);
          return returnTable$1;
        }
        check.assert(false, "lookup type 6 format must be 1, 2 or 3.");
      };
      function makeGsubTable(gsub2) {
        return new table2.Table("GSUB", [
          { name: "version", type: "ULONG", value: 65536 },
          { name: "scripts", type: "TABLE", value: new table2.ScriptList(gsub2.scripts) },
          { name: "features", type: "TABLE", value: new table2.FeatureList(gsub2.features) },
          { name: "lookups", type: "TABLE", value: new table2.LookupList(gsub2.lookups, subtableMakers) }
        ]);
      }
      var gsub = { parse: parseGsubTable, make: makeGsubTable };
      function parseMetaTable(data, start) {
        var p = new parse2.Parser(data, start);
        var tableVersion = p.parseULong();
        check.argument(tableVersion === 1, "Unsupported META table version.");
        p.parseULong();
        p.parseULong();
        var numDataMaps = p.parseULong();
        var tags = {};
        for (var i = 0; i < numDataMaps; i++) {
          var tag = p.parseTag();
          var dataOffset = p.parseULong();
          var dataLength = p.parseULong();
          var text2 = decode.UTF8(data, start + dataOffset, dataLength);
          tags[tag] = text2;
        }
        return tags;
      }
      function makeMetaTable(tags) {
        var numTags = Object.keys(tags).length;
        var stringPool = "";
        var stringPoolOffset = 16 + numTags * 12;
        var result = new table2.Table("meta", [
          { name: "version", type: "ULONG", value: 1 },
          { name: "flags", type: "ULONG", value: 0 },
          { name: "offset", type: "ULONG", value: stringPoolOffset },
          { name: "numTags", type: "ULONG", value: numTags }
        ]);
        for (var tag in tags) {
          var pos = stringPool.length;
          stringPool += tags[tag];
          result.fields.push({ name: "tag " + tag, type: "TAG", value: tag });
          result.fields.push({ name: "offset " + tag, type: "ULONG", value: stringPoolOffset + pos });
          result.fields.push({ name: "length " + tag, type: "ULONG", value: tags[tag].length });
        }
        result.fields.push({ name: "stringPool", type: "CHARARRAY", value: stringPool });
        return result;
      }
      var meta = { parse: parseMetaTable, make: makeMetaTable };
      function log2(v) {
        return Math.log(v) / Math.log(2) | 0;
      }
      function computeCheckSum(bytes) {
        while (bytes.length % 4 !== 0) {
          bytes.push(0);
        }
        var sum = 0;
        for (var i = 0; i < bytes.length; i += 4) {
          sum += (bytes[i] << 24) + (bytes[i + 1] << 16) + (bytes[i + 2] << 8) + bytes[i + 3];
        }
        sum %= Math.pow(2, 32);
        return sum;
      }
      function makeTableRecord(tag, checkSum, offset, length) {
        return new table2.Record("Table Record", [
          { name: "tag", type: "TAG", value: tag !== void 0 ? tag : "" },
          { name: "checkSum", type: "ULONG", value: checkSum !== void 0 ? checkSum : 0 },
          { name: "offset", type: "ULONG", value: offset !== void 0 ? offset : 0 },
          { name: "length", type: "ULONG", value: length !== void 0 ? length : 0 }
        ]);
      }
      function makeSfntTable(tables2) {
        var sfnt2 = new table2.Table("sfnt", [
          { name: "version", type: "TAG", value: "OTTO" },
          { name: "numTables", type: "USHORT", value: 0 },
          { name: "searchRange", type: "USHORT", value: 0 },
          { name: "entrySelector", type: "USHORT", value: 0 },
          { name: "rangeShift", type: "USHORT", value: 0 }
        ]);
        sfnt2.tables = tables2;
        sfnt2.numTables = tables2.length;
        var highestPowerOf2 = Math.pow(2, log2(sfnt2.numTables));
        sfnt2.searchRange = 16 * highestPowerOf2;
        sfnt2.entrySelector = log2(highestPowerOf2);
        sfnt2.rangeShift = sfnt2.numTables * 16 - sfnt2.searchRange;
        var recordFields = [];
        var tableFields = [];
        var offset = sfnt2.sizeOf() + makeTableRecord().sizeOf() * sfnt2.numTables;
        while (offset % 4 !== 0) {
          offset += 1;
          tableFields.push({ name: "padding", type: "BYTE", value: 0 });
        }
        for (var i = 0; i < tables2.length; i += 1) {
          var t = tables2[i];
          check.argument(t.tableName.length === 4, "Table name" + t.tableName + " is invalid.");
          var tableLength = t.sizeOf();
          var tableRecord = makeTableRecord(t.tableName, computeCheckSum(t.encode()), offset, tableLength);
          recordFields.push({ name: tableRecord.tag + " Table Record", type: "RECORD", value: tableRecord });
          tableFields.push({ name: t.tableName + " table", type: "RECORD", value: t });
          offset += tableLength;
          check.argument(!isNaN(offset), "Something went wrong calculating the offset.");
          while (offset % 4 !== 0) {
            offset += 1;
            tableFields.push({ name: "padding", type: "BYTE", value: 0 });
          }
        }
        recordFields.sort(function(r1, r2) {
          if (r1.value.tag > r2.value.tag) {
            return 1;
          } else {
            return -1;
          }
        });
        sfnt2.fields = sfnt2.fields.concat(recordFields);
        sfnt2.fields = sfnt2.fields.concat(tableFields);
        return sfnt2;
      }
      function metricsForChar(font, chars, notFoundMetrics) {
        for (var i = 0; i < chars.length; i += 1) {
          var glyphIndex = font.charToGlyphIndex(chars[i]);
          if (glyphIndex > 0) {
            var glyph = font.glyphs.get(glyphIndex);
            return glyph.getMetrics();
          }
        }
        return notFoundMetrics;
      }
      function average(vs) {
        var sum = 0;
        for (var i = 0; i < vs.length; i += 1) {
          sum += vs[i];
        }
        return sum / vs.length;
      }
      function fontToSfntTable(font) {
        var xMins = [];
        var yMins = [];
        var xMaxs = [];
        var yMaxs = [];
        var advanceWidths = [];
        var leftSideBearings = [];
        var rightSideBearings = [];
        var firstCharIndex;
        var lastCharIndex = 0;
        var ulUnicodeRange1 = 0;
        var ulUnicodeRange2 = 0;
        var ulUnicodeRange3 = 0;
        var ulUnicodeRange4 = 0;
        for (var i = 0; i < font.glyphs.length; i += 1) {
          var glyph = font.glyphs.get(i);
          var unicode = glyph.unicode | 0;
          if (isNaN(glyph.advanceWidth)) {
            throw new Error("Glyph " + glyph.name + " (" + i + "): advanceWidth is not a number.");
          }
          if (firstCharIndex > unicode || firstCharIndex === void 0) {
            if (unicode > 0) {
              firstCharIndex = unicode;
            }
          }
          if (lastCharIndex < unicode) {
            lastCharIndex = unicode;
          }
          var position = os2.getUnicodeRange(unicode);
          if (position < 32) {
            ulUnicodeRange1 |= 1 << position;
          } else if (position < 64) {
            ulUnicodeRange2 |= 1 << position - 32;
          } else if (position < 96) {
            ulUnicodeRange3 |= 1 << position - 64;
          } else if (position < 123) {
            ulUnicodeRange4 |= 1 << position - 96;
          } else {
            throw new Error("Unicode ranges bits > 123 are reserved for internal usage");
          }
          if (glyph.name === ".notdef") {
            continue;
          }
          var metrics = glyph.getMetrics();
          xMins.push(metrics.xMin);
          yMins.push(metrics.yMin);
          xMaxs.push(metrics.xMax);
          yMaxs.push(metrics.yMax);
          leftSideBearings.push(metrics.leftSideBearing);
          rightSideBearings.push(metrics.rightSideBearing);
          advanceWidths.push(glyph.advanceWidth);
        }
        var globals = {
          xMin: Math.min.apply(null, xMins),
          yMin: Math.min.apply(null, yMins),
          xMax: Math.max.apply(null, xMaxs),
          yMax: Math.max.apply(null, yMaxs),
          advanceWidthMax: Math.max.apply(null, advanceWidths),
          advanceWidthAvg: average(advanceWidths),
          minLeftSideBearing: Math.min.apply(null, leftSideBearings),
          maxLeftSideBearing: Math.max.apply(null, leftSideBearings),
          minRightSideBearing: Math.min.apply(null, rightSideBearings)
        };
        globals.ascender = font.ascender;
        globals.descender = font.descender;
        var headTable = head.make({
          flags: 3,
          // 00000011 (baseline for font at y=0; left sidebearing point at x=0)
          unitsPerEm: font.unitsPerEm,
          xMin: globals.xMin,
          yMin: globals.yMin,
          xMax: globals.xMax,
          yMax: globals.yMax,
          lowestRecPPEM: 3,
          createdTimestamp: font.createdTimestamp
        });
        var hheaTable = hhea.make({
          ascender: globals.ascender,
          descender: globals.descender,
          advanceWidthMax: globals.advanceWidthMax,
          minLeftSideBearing: globals.minLeftSideBearing,
          minRightSideBearing: globals.minRightSideBearing,
          xMaxExtent: globals.maxLeftSideBearing + (globals.xMax - globals.xMin),
          numberOfHMetrics: font.glyphs.length
        });
        var maxpTable = maxp.make(font.glyphs.length);
        var os2Table = os2.make(Object.assign({
          xAvgCharWidth: Math.round(globals.advanceWidthAvg),
          usFirstCharIndex: firstCharIndex,
          usLastCharIndex: lastCharIndex,
          ulUnicodeRange1,
          ulUnicodeRange2,
          ulUnicodeRange3,
          ulUnicodeRange4,
          // See http://typophile.com/node/13081 for more info on vertical metrics.
          // We get metrics for typical characters (such as "x" for xHeight).
          // We provide some fallback characters if characters are unavailable: their
          // ordering was chosen experimentally.
          sTypoAscender: globals.ascender,
          sTypoDescender: globals.descender,
          sTypoLineGap: 0,
          usWinAscent: globals.yMax,
          usWinDescent: Math.abs(globals.yMin),
          ulCodePageRange1: 1,
          // FIXME: hard-code Latin 1 support for now
          sxHeight: metricsForChar(font, "xyvw", { yMax: Math.round(globals.ascender / 2) }).yMax,
          sCapHeight: metricsForChar(font, "HIKLEFJMNTZBDPRAGOQSUVWXY", globals).yMax,
          usDefaultChar: font.hasChar(" ") ? 32 : 0,
          // Use space as the default character, if available.
          usBreakChar: font.hasChar(" ") ? 32 : 0
          // Use space as the break character, if available.
        }, font.tables.os2));
        var hmtxTable = hmtx.make(font.glyphs);
        var cmapTable = cmap.make(font.glyphs);
        var englishFamilyName = font.getEnglishName("fontFamily");
        var englishStyleName = font.getEnglishName("fontSubfamily");
        var englishFullName = englishFamilyName + " " + englishStyleName;
        var postScriptName = font.getEnglishName("postScriptName");
        if (!postScriptName) {
          postScriptName = englishFamilyName.replace(/\s/g, "") + "-" + englishStyleName;
        }
        var names = {};
        for (var n in font.names) {
          names[n] = font.names[n];
        }
        if (!names.uniqueID) {
          names.uniqueID = { en: font.getEnglishName("manufacturer") + ":" + englishFullName };
        }
        if (!names.postScriptName) {
          names.postScriptName = { en: postScriptName };
        }
        if (!names.preferredFamily) {
          names.preferredFamily = font.names.fontFamily;
        }
        if (!names.preferredSubfamily) {
          names.preferredSubfamily = font.names.fontSubfamily;
        }
        var languageTags = [];
        var nameTable = _name.make(names, languageTags);
        var ltagTable = languageTags.length > 0 ? ltag.make(languageTags) : void 0;
        var postTable = post.make();
        var cffTable = cff.make(font.glyphs, {
          version: font.getEnglishName("version"),
          fullName: englishFullName,
          familyName: englishFamilyName,
          weightName: englishStyleName,
          postScriptName,
          unitsPerEm: font.unitsPerEm,
          fontBBox: [0, globals.yMin, globals.ascender, globals.advanceWidthMax]
        });
        var metaTable = font.metas && Object.keys(font.metas).length > 0 ? meta.make(font.metas) : void 0;
        var tables2 = [headTable, hheaTable, maxpTable, os2Table, nameTable, cmapTable, postTable, cffTable, hmtxTable];
        if (ltagTable) {
          tables2.push(ltagTable);
        }
        if (font.tables.gsub) {
          tables2.push(gsub.make(font.tables.gsub));
        }
        if (metaTable) {
          tables2.push(metaTable);
        }
        var sfntTable = makeSfntTable(tables2);
        var bytes = sfntTable.encode();
        var checkSum = computeCheckSum(bytes);
        var tableFields = sfntTable.fields;
        var checkSumAdjusted = false;
        for (var i$1 = 0; i$1 < tableFields.length; i$1 += 1) {
          if (tableFields[i$1].name === "head table") {
            tableFields[i$1].value.checkSumAdjustment = 2981146554 - checkSum;
            checkSumAdjusted = true;
            break;
          }
        }
        if (!checkSumAdjusted) {
          throw new Error("Could not find head table with checkSum to adjust.");
        }
        return sfntTable;
      }
      var sfnt = { make: makeSfntTable, fontToTable: fontToSfntTable, computeCheckSum };
      function searchTag(arr, tag) {
        var imin = 0;
        var imax = arr.length - 1;
        while (imin <= imax) {
          var imid = imin + imax >>> 1;
          var val = arr[imid].tag;
          if (val === tag) {
            return imid;
          } else if (val < tag) {
            imin = imid + 1;
          } else {
            imax = imid - 1;
          }
        }
        return -imin - 1;
      }
      function binSearch(arr, value) {
        var imin = 0;
        var imax = arr.length - 1;
        while (imin <= imax) {
          var imid = imin + imax >>> 1;
          var val = arr[imid];
          if (val === value) {
            return imid;
          } else if (val < value) {
            imin = imid + 1;
          } else {
            imax = imid - 1;
          }
        }
        return -imin - 1;
      }
      function searchRange(ranges, value) {
        var range;
        var imin = 0;
        var imax = ranges.length - 1;
        while (imin <= imax) {
          var imid = imin + imax >>> 1;
          range = ranges[imid];
          var start = range.start;
          if (start === value) {
            return range;
          } else if (start < value) {
            imin = imid + 1;
          } else {
            imax = imid - 1;
          }
        }
        if (imin > 0) {
          range = ranges[imin - 1];
          if (value > range.end) {
            return 0;
          }
          return range;
        }
      }
      function Layout(font, tableName) {
        this.font = font;
        this.tableName = tableName;
      }
      Layout.prototype = {
        /**
         * Binary search an object by "tag" property
         * @instance
         * @function searchTag
         * @memberof opentype.Layout
         * @param  {Array} arr
         * @param  {string} tag
         * @return {number}
         */
        searchTag,
        /**
         * Binary search in a list of numbers
         * @instance
         * @function binSearch
         * @memberof opentype.Layout
         * @param  {Array} arr
         * @param  {number} value
         * @return {number}
         */
        binSearch,
        /**
         * Get or create the Layout table (GSUB, GPOS etc).
         * @param  {boolean} create - Whether to create a new one.
         * @return {Object} The GSUB or GPOS table.
         */
        getTable: function(create) {
          var layout = this.font.tables[this.tableName];
          if (!layout && create) {
            layout = this.font.tables[this.tableName] = this.createDefaultTable();
          }
          return layout;
        },
        /**
         * Returns all scripts in the substitution table.
         * @instance
         * @return {Array}
         */
        getScriptNames: function() {
          var layout = this.getTable();
          if (!layout) {
            return [];
          }
          return layout.scripts.map(function(script) {
            return script.tag;
          });
        },
        /**
         * Returns the best bet for a script name.
         * Returns 'DFLT' if it exists.
         * If not, returns 'latn' if it exists.
         * If neither exist, returns undefined.
         */
        getDefaultScriptName: function() {
          var layout = this.getTable();
          if (!layout) {
            return;
          }
          var hasLatn = false;
          for (var i = 0; i < layout.scripts.length; i++) {
            var name = layout.scripts[i].tag;
            if (name === "DFLT") {
              return name;
            }
            if (name === "latn") {
              hasLatn = true;
            }
          }
          if (hasLatn) {
            return "latn";
          }
        },
        /**
         * Returns all LangSysRecords in the given script.
         * @instance
         * @param {string} [script='DFLT']
         * @param {boolean} create - forces the creation of this script table if it doesn't exist.
         * @return {Object} An object with tag and script properties.
         */
        getScriptTable: function(script, create) {
          var layout = this.getTable(create);
          if (layout) {
            script = script || "DFLT";
            var scripts = layout.scripts;
            var pos = searchTag(layout.scripts, script);
            if (pos >= 0) {
              return scripts[pos].script;
            } else if (create) {
              var scr = {
                tag: script,
                script: {
                  defaultLangSys: { reserved: 0, reqFeatureIndex: 65535, featureIndexes: [] },
                  langSysRecords: []
                }
              };
              scripts.splice(-1 - pos, 0, scr);
              return scr.script;
            }
          }
        },
        /**
         * Returns a language system table
         * @instance
         * @param {string} [script='DFLT']
         * @param {string} [language='dlft']
         * @param {boolean} create - forces the creation of this langSysTable if it doesn't exist.
         * @return {Object}
         */
        getLangSysTable: function(script, language, create) {
          var scriptTable = this.getScriptTable(script, create);
          if (scriptTable) {
            if (!language || language === "dflt" || language === "DFLT") {
              return scriptTable.defaultLangSys;
            }
            var pos = searchTag(scriptTable.langSysRecords, language);
            if (pos >= 0) {
              return scriptTable.langSysRecords[pos].langSys;
            } else if (create) {
              var langSysRecord = {
                tag: language,
                langSys: { reserved: 0, reqFeatureIndex: 65535, featureIndexes: [] }
              };
              scriptTable.langSysRecords.splice(-1 - pos, 0, langSysRecord);
              return langSysRecord.langSys;
            }
          }
        },
        /**
         * Get a specific feature table.
         * @instance
         * @param {string} [script='DFLT']
         * @param {string} [language='dlft']
         * @param {string} feature - One of the codes listed at https://www.microsoft.com/typography/OTSPEC/featurelist.htm
         * @param {boolean} create - forces the creation of the feature table if it doesn't exist.
         * @return {Object}
         */
        getFeatureTable: function(script, language, feature, create) {
          var langSysTable2 = this.getLangSysTable(script, language, create);
          if (langSysTable2) {
            var featureRecord;
            var featIndexes = langSysTable2.featureIndexes;
            var allFeatures = this.font.tables[this.tableName].features;
            for (var i = 0; i < featIndexes.length; i++) {
              featureRecord = allFeatures[featIndexes[i]];
              if (featureRecord.tag === feature) {
                return featureRecord.feature;
              }
            }
            if (create) {
              var index = allFeatures.length;
              check.assert(index === 0 || feature >= allFeatures[index - 1].tag, "Features must be added in alphabetical order.");
              featureRecord = {
                tag: feature,
                feature: { params: 0, lookupListIndexes: [] }
              };
              allFeatures.push(featureRecord);
              featIndexes.push(index);
              return featureRecord.feature;
            }
          }
        },
        /**
         * Get the lookup tables of a given type for a script/language/feature.
         * @instance
         * @param {string} [script='DFLT']
         * @param {string} [language='dlft']
         * @param {string} feature - 4-letter feature code
         * @param {number} lookupType - 1 to 9
         * @param {boolean} create - forces the creation of the lookup table if it doesn't exist, with no subtables.
         * @return {Object[]}
         */
        getLookupTables: function(script, language, feature, lookupType, create) {
          var featureTable = this.getFeatureTable(script, language, feature, create);
          var tables2 = [];
          if (featureTable) {
            var lookupTable;
            var lookupListIndexes = featureTable.lookupListIndexes;
            var allLookups = this.font.tables[this.tableName].lookups;
            for (var i = 0; i < lookupListIndexes.length; i++) {
              lookupTable = allLookups[lookupListIndexes[i]];
              if (lookupTable.lookupType === lookupType) {
                tables2.push(lookupTable);
              }
            }
            if (tables2.length === 0 && create) {
              lookupTable = {
                lookupType,
                lookupFlag: 0,
                subtables: [],
                markFilteringSet: void 0
              };
              var index = allLookups.length;
              allLookups.push(lookupTable);
              lookupListIndexes.push(index);
              return [lookupTable];
            }
          }
          return tables2;
        },
        /**
         * Find a glyph in a class definition table
         * https://docs.microsoft.com/en-us/typography/opentype/spec/chapter2#class-definition-table
         * @param {object} classDefTable - an OpenType Layout class definition table
         * @param {number} glyphIndex - the index of the glyph to find
         * @returns {number} -1 if not found
         */
        getGlyphClass: function(classDefTable, glyphIndex) {
          switch (classDefTable.format) {
            case 1:
              if (classDefTable.startGlyph <= glyphIndex && glyphIndex < classDefTable.startGlyph + classDefTable.classes.length) {
                return classDefTable.classes[glyphIndex - classDefTable.startGlyph];
              }
              return 0;
            case 2:
              var range = searchRange(classDefTable.ranges, glyphIndex);
              return range ? range.classId : 0;
          }
        },
        /**
         * Find a glyph in a coverage table
         * https://docs.microsoft.com/en-us/typography/opentype/spec/chapter2#coverage-table
         * @param {object} coverageTable - an OpenType Layout coverage table
         * @param {number} glyphIndex - the index of the glyph to find
         * @returns {number} -1 if not found
         */
        getCoverageIndex: function(coverageTable, glyphIndex) {
          switch (coverageTable.format) {
            case 1:
              var index = binSearch(coverageTable.glyphs, glyphIndex);
              return index >= 0 ? index : -1;
            case 2:
              var range = searchRange(coverageTable.ranges, glyphIndex);
              return range ? range.index + glyphIndex - range.start : -1;
          }
        },
        /**
         * Returns the list of glyph indexes of a coverage table.
         * Format 1: the list is stored raw
         * Format 2: compact list as range records.
         * @instance
         * @param  {Object} coverageTable
         * @return {Array}
         */
        expandCoverage: function(coverageTable) {
          if (coverageTable.format === 1) {
            return coverageTable.glyphs;
          } else {
            var glyphs = [];
            var ranges = coverageTable.ranges;
            for (var i = 0; i < ranges.length; i++) {
              var range = ranges[i];
              var start = range.start;
              var end = range.end;
              for (var j = start; j <= end; j++) {
                glyphs.push(j);
              }
            }
            return glyphs;
          }
        }
      };
      function Position(font) {
        Layout.call(this, font, "gpos");
      }
      Position.prototype = Layout.prototype;
      Position.prototype.init = function() {
        var script = this.getDefaultScriptName();
        this.defaultKerningTables = this.getKerningTables(script);
      };
      Position.prototype.getKerningValue = function(kerningLookups, leftIndex, rightIndex) {
        for (var i = 0; i < kerningLookups.length; i++) {
          var subtables = kerningLookups[i].subtables;
          for (var j = 0; j < subtables.length; j++) {
            var subtable = subtables[j];
            var covIndex = this.getCoverageIndex(subtable.coverage, leftIndex);
            if (covIndex < 0) {
              continue;
            }
            switch (subtable.posFormat) {
              case 1:
                var pairSet = subtable.pairSets[covIndex];
                for (var k = 0; k < pairSet.length; k++) {
                  var pair = pairSet[k];
                  if (pair.secondGlyph === rightIndex) {
                    return pair.value1 && pair.value1.xAdvance || 0;
                  }
                }
                break;
              // left glyph found, not right glyph - try next subtable
              case 2:
                var class1 = this.getGlyphClass(subtable.classDef1, leftIndex);
                var class2 = this.getGlyphClass(subtable.classDef2, rightIndex);
                var pair$1 = subtable.classRecords[class1][class2];
                return pair$1.value1 && pair$1.value1.xAdvance || 0;
            }
          }
        }
        return 0;
      };
      Position.prototype.getKerningTables = function(script, language) {
        if (this.font.tables.gpos) {
          return this.getLookupTables(script, language, "kern", 2);
        }
      };
      function Substitution(font) {
        Layout.call(this, font, "gsub");
      }
      function arraysEqual(ar1, ar2) {
        var n = ar1.length;
        if (n !== ar2.length) {
          return false;
        }
        for (var i = 0; i < n; i++) {
          if (ar1[i] !== ar2[i]) {
            return false;
          }
        }
        return true;
      }
      function getSubstFormat(lookupTable, format, defaultSubtable) {
        var subtables = lookupTable.subtables;
        for (var i = 0; i < subtables.length; i++) {
          var subtable = subtables[i];
          if (subtable.substFormat === format) {
            return subtable;
          }
        }
        if (defaultSubtable) {
          subtables.push(defaultSubtable);
          return defaultSubtable;
        }
        return void 0;
      }
      Substitution.prototype = Layout.prototype;
      Substitution.prototype.createDefaultTable = function() {
        return {
          version: 1,
          scripts: [{
            tag: "DFLT",
            script: {
              defaultLangSys: { reserved: 0, reqFeatureIndex: 65535, featureIndexes: [] },
              langSysRecords: []
            }
          }],
          features: [],
          lookups: []
        };
      };
      Substitution.prototype.getSingle = function(feature, script, language) {
        var substitutions = [];
        var lookupTables = this.getLookupTables(script, language, feature, 1);
        for (var idx = 0; idx < lookupTables.length; idx++) {
          var subtables = lookupTables[idx].subtables;
          for (var i = 0; i < subtables.length; i++) {
            var subtable = subtables[i];
            var glyphs = this.expandCoverage(subtable.coverage);
            var j = void 0;
            if (subtable.substFormat === 1) {
              var delta = subtable.deltaGlyphId;
              for (j = 0; j < glyphs.length; j++) {
                var glyph = glyphs[j];
                substitutions.push({ sub: glyph, by: glyph + delta });
              }
            } else {
              var substitute = subtable.substitute;
              for (j = 0; j < glyphs.length; j++) {
                substitutions.push({ sub: glyphs[j], by: substitute[j] });
              }
            }
          }
        }
        return substitutions;
      };
      Substitution.prototype.getMultiple = function(feature, script, language) {
        var substitutions = [];
        var lookupTables = this.getLookupTables(script, language, feature, 2);
        for (var idx = 0; idx < lookupTables.length; idx++) {
          var subtables = lookupTables[idx].subtables;
          for (var i = 0; i < subtables.length; i++) {
            var subtable = subtables[i];
            var glyphs = this.expandCoverage(subtable.coverage);
            var j = void 0;
            for (j = 0; j < glyphs.length; j++) {
              var glyph = glyphs[j];
              var replacements = subtable.sequences[j];
              substitutions.push({ sub: glyph, by: replacements });
            }
          }
        }
        return substitutions;
      };
      Substitution.prototype.getAlternates = function(feature, script, language) {
        var alternates = [];
        var lookupTables = this.getLookupTables(script, language, feature, 3);
        for (var idx = 0; idx < lookupTables.length; idx++) {
          var subtables = lookupTables[idx].subtables;
          for (var i = 0; i < subtables.length; i++) {
            var subtable = subtables[i];
            var glyphs = this.expandCoverage(subtable.coverage);
            var alternateSets = subtable.alternateSets;
            for (var j = 0; j < glyphs.length; j++) {
              alternates.push({ sub: glyphs[j], by: alternateSets[j] });
            }
          }
        }
        return alternates;
      };
      Substitution.prototype.getLigatures = function(feature, script, language) {
        var ligatures = [];
        var lookupTables = this.getLookupTables(script, language, feature, 4);
        for (var idx = 0; idx < lookupTables.length; idx++) {
          var subtables = lookupTables[idx].subtables;
          for (var i = 0; i < subtables.length; i++) {
            var subtable = subtables[i];
            var glyphs = this.expandCoverage(subtable.coverage);
            var ligatureSets = subtable.ligatureSets;
            for (var j = 0; j < glyphs.length; j++) {
              var startGlyph = glyphs[j];
              var ligSet = ligatureSets[j];
              for (var k = 0; k < ligSet.length; k++) {
                var lig = ligSet[k];
                ligatures.push({
                  sub: [startGlyph].concat(lig.components),
                  by: lig.ligGlyph
                });
              }
            }
          }
        }
        return ligatures;
      };
      Substitution.prototype.addSingle = function(feature, substitution, script, language) {
        var lookupTable = this.getLookupTables(script, language, feature, 1, true)[0];
        var subtable = getSubstFormat(lookupTable, 2, {
          // lookup type 1 subtable, format 2, coverage format 1
          substFormat: 2,
          coverage: { format: 1, glyphs: [] },
          substitute: []
        });
        check.assert(subtable.coverage.format === 1, "Single: unable to modify coverage table format " + subtable.coverage.format);
        var coverageGlyph = substitution.sub;
        var pos = this.binSearch(subtable.coverage.glyphs, coverageGlyph);
        if (pos < 0) {
          pos = -1 - pos;
          subtable.coverage.glyphs.splice(pos, 0, coverageGlyph);
          subtable.substitute.splice(pos, 0, 0);
        }
        subtable.substitute[pos] = substitution.by;
      };
      Substitution.prototype.addMultiple = function(feature, substitution, script, language) {
        check.assert(substitution.by instanceof Array && substitution.by.length > 1, 'Multiple: "by" must be an array of two or more ids');
        var lookupTable = this.getLookupTables(script, language, feature, 2, true)[0];
        var subtable = getSubstFormat(lookupTable, 1, {
          // lookup type 2 subtable, format 1, coverage format 1
          substFormat: 1,
          coverage: { format: 1, glyphs: [] },
          sequences: []
        });
        check.assert(subtable.coverage.format === 1, "Multiple: unable to modify coverage table format " + subtable.coverage.format);
        var coverageGlyph = substitution.sub;
        var pos = this.binSearch(subtable.coverage.glyphs, coverageGlyph);
        if (pos < 0) {
          pos = -1 - pos;
          subtable.coverage.glyphs.splice(pos, 0, coverageGlyph);
          subtable.sequences.splice(pos, 0, 0);
        }
        subtable.sequences[pos] = substitution.by;
      };
      Substitution.prototype.addAlternate = function(feature, substitution, script, language) {
        var lookupTable = this.getLookupTables(script, language, feature, 3, true)[0];
        var subtable = getSubstFormat(lookupTable, 1, {
          // lookup type 3 subtable, format 1, coverage format 1
          substFormat: 1,
          coverage: { format: 1, glyphs: [] },
          alternateSets: []
        });
        check.assert(subtable.coverage.format === 1, "Alternate: unable to modify coverage table format " + subtable.coverage.format);
        var coverageGlyph = substitution.sub;
        var pos = this.binSearch(subtable.coverage.glyphs, coverageGlyph);
        if (pos < 0) {
          pos = -1 - pos;
          subtable.coverage.glyphs.splice(pos, 0, coverageGlyph);
          subtable.alternateSets.splice(pos, 0, 0);
        }
        subtable.alternateSets[pos] = substitution.by;
      };
      Substitution.prototype.addLigature = function(feature, ligature, script, language) {
        var lookupTable = this.getLookupTables(script, language, feature, 4, true)[0];
        var subtable = lookupTable.subtables[0];
        if (!subtable) {
          subtable = {
            // lookup type 4 subtable, format 1, coverage format 1
            substFormat: 1,
            coverage: { format: 1, glyphs: [] },
            ligatureSets: []
          };
          lookupTable.subtables[0] = subtable;
        }
        check.assert(subtable.coverage.format === 1, "Ligature: unable to modify coverage table format " + subtable.coverage.format);
        var coverageGlyph = ligature.sub[0];
        var ligComponents = ligature.sub.slice(1);
        var ligatureTable = {
          ligGlyph: ligature.by,
          components: ligComponents
        };
        var pos = this.binSearch(subtable.coverage.glyphs, coverageGlyph);
        if (pos >= 0) {
          var ligatureSet = subtable.ligatureSets[pos];
          for (var i = 0; i < ligatureSet.length; i++) {
            if (arraysEqual(ligatureSet[i].components, ligComponents)) {
              return;
            }
          }
          ligatureSet.push(ligatureTable);
        } else {
          pos = -1 - pos;
          subtable.coverage.glyphs.splice(pos, 0, coverageGlyph);
          subtable.ligatureSets.splice(pos, 0, [ligatureTable]);
        }
      };
      Substitution.prototype.getFeature = function(feature, script, language) {
        if (/ss\d\d/.test(feature)) {
          return this.getSingle(feature, script, language);
        }
        switch (feature) {
          case "aalt":
          case "salt":
            return this.getSingle(feature, script, language).concat(this.getAlternates(feature, script, language));
          case "dlig":
          case "liga":
          case "rlig":
            return this.getLigatures(feature, script, language);
          case "ccmp":
            return this.getMultiple(feature, script, language).concat(this.getLigatures(feature, script, language));
          case "stch":
            return this.getMultiple(feature, script, language);
        }
        return void 0;
      };
      Substitution.prototype.add = function(feature, sub, script, language) {
        if (/ss\d\d/.test(feature)) {
          return this.addSingle(feature, sub, script, language);
        }
        switch (feature) {
          case "aalt":
          case "salt":
            if (typeof sub.by === "number") {
              return this.addSingle(feature, sub, script, language);
            }
            return this.addAlternate(feature, sub, script, language);
          case "dlig":
          case "liga":
          case "rlig":
            return this.addLigature(feature, sub, script, language);
          case "ccmp":
            if (sub.by instanceof Array) {
              return this.addMultiple(feature, sub, script, language);
            }
            return this.addLigature(feature, sub, script, language);
        }
        return void 0;
      };
      function isBrowser() {
        return typeof window !== "undefined";
      }
      function nodeBufferToArrayBuffer(buffer2) {
        var ab = new ArrayBuffer(buffer2.length);
        var view = new Uint8Array(ab);
        for (var i = 0; i < buffer2.length; ++i) {
          view[i] = buffer2[i];
        }
        return ab;
      }
      function arrayBufferToNodeBuffer(ab) {
        var buffer2 = new Buffer(ab.byteLength);
        var view = new Uint8Array(ab);
        for (var i = 0; i < buffer2.length; ++i) {
          buffer2[i] = view[i];
        }
        return buffer2;
      }
      function checkArgument(expression, message) {
        if (!expression) {
          throw message;
        }
      }
      function parseGlyphCoordinate(p, flag, previousValue, shortVectorBitMask, sameBitMask) {
        var v;
        if ((flag & shortVectorBitMask) > 0) {
          v = p.parseByte();
          if ((flag & sameBitMask) === 0) {
            v = -v;
          }
          v = previousValue + v;
        } else {
          if ((flag & sameBitMask) > 0) {
            v = previousValue;
          } else {
            v = previousValue + p.parseShort();
          }
        }
        return v;
      }
      function parseGlyph(glyph, data, start) {
        var p = new parse2.Parser(data, start);
        glyph.numberOfContours = p.parseShort();
        glyph._xMin = p.parseShort();
        glyph._yMin = p.parseShort();
        glyph._xMax = p.parseShort();
        glyph._yMax = p.parseShort();
        var flags;
        var flag;
        if (glyph.numberOfContours > 0) {
          var endPointIndices = glyph.endPointIndices = [];
          for (var i = 0; i < glyph.numberOfContours; i += 1) {
            endPointIndices.push(p.parseUShort());
          }
          glyph.instructionLength = p.parseUShort();
          glyph.instructions = [];
          for (var i$1 = 0; i$1 < glyph.instructionLength; i$1 += 1) {
            glyph.instructions.push(p.parseByte());
          }
          var numberOfCoordinates = endPointIndices[endPointIndices.length - 1] + 1;
          flags = [];
          for (var i$2 = 0; i$2 < numberOfCoordinates; i$2 += 1) {
            flag = p.parseByte();
            flags.push(flag);
            if ((flag & 8) > 0) {
              var repeatCount = p.parseByte();
              for (var j = 0; j < repeatCount; j += 1) {
                flags.push(flag);
                i$2 += 1;
              }
            }
          }
          check.argument(flags.length === numberOfCoordinates, "Bad flags.");
          if (endPointIndices.length > 0) {
            var points = [];
            var point;
            if (numberOfCoordinates > 0) {
              for (var i$3 = 0; i$3 < numberOfCoordinates; i$3 += 1) {
                flag = flags[i$3];
                point = {};
                point.onCurve = !!(flag & 1);
                point.lastPointOfContour = endPointIndices.indexOf(i$3) >= 0;
                points.push(point);
              }
              var px = 0;
              for (var i$4 = 0; i$4 < numberOfCoordinates; i$4 += 1) {
                flag = flags[i$4];
                point = points[i$4];
                point.x = parseGlyphCoordinate(p, flag, px, 2, 16);
                px = point.x;
              }
              var py = 0;
              for (var i$5 = 0; i$5 < numberOfCoordinates; i$5 += 1) {
                flag = flags[i$5];
                point = points[i$5];
                point.y = parseGlyphCoordinate(p, flag, py, 4, 32);
                py = point.y;
              }
            }
            glyph.points = points;
          } else {
            glyph.points = [];
          }
        } else if (glyph.numberOfContours === 0) {
          glyph.points = [];
        } else {
          glyph.isComposite = true;
          glyph.points = [];
          glyph.components = [];
          var moreComponents = true;
          while (moreComponents) {
            flags = p.parseUShort();
            var component = {
              glyphIndex: p.parseUShort(),
              xScale: 1,
              scale01: 0,
              scale10: 0,
              yScale: 1,
              dx: 0,
              dy: 0
            };
            if ((flags & 1) > 0) {
              if ((flags & 2) > 0) {
                component.dx = p.parseShort();
                component.dy = p.parseShort();
              } else {
                component.matchedPoints = [p.parseUShort(), p.parseUShort()];
              }
            } else {
              if ((flags & 2) > 0) {
                component.dx = p.parseChar();
                component.dy = p.parseChar();
              } else {
                component.matchedPoints = [p.parseByte(), p.parseByte()];
              }
            }
            if ((flags & 8) > 0) {
              component.xScale = component.yScale = p.parseF2Dot14();
            } else if ((flags & 64) > 0) {
              component.xScale = p.parseF2Dot14();
              component.yScale = p.parseF2Dot14();
            } else if ((flags & 128) > 0) {
              component.xScale = p.parseF2Dot14();
              component.scale01 = p.parseF2Dot14();
              component.scale10 = p.parseF2Dot14();
              component.yScale = p.parseF2Dot14();
            }
            glyph.components.push(component);
            moreComponents = !!(flags & 32);
          }
          if (flags & 256) {
            glyph.instructionLength = p.parseUShort();
            glyph.instructions = [];
            for (var i$6 = 0; i$6 < glyph.instructionLength; i$6 += 1) {
              glyph.instructions.push(p.parseByte());
            }
          }
        }
      }
      function transformPoints(points, transform) {
        var newPoints = [];
        for (var i = 0; i < points.length; i += 1) {
          var pt = points[i];
          var newPt = {
            x: transform.xScale * pt.x + transform.scale01 * pt.y + transform.dx,
            y: transform.scale10 * pt.x + transform.yScale * pt.y + transform.dy,
            onCurve: pt.onCurve,
            lastPointOfContour: pt.lastPointOfContour
          };
          newPoints.push(newPt);
        }
        return newPoints;
      }
      function getContours(points) {
        var contours = [];
        var currentContour = [];
        for (var i = 0; i < points.length; i += 1) {
          var pt = points[i];
          currentContour.push(pt);
          if (pt.lastPointOfContour) {
            contours.push(currentContour);
            currentContour = [];
          }
        }
        check.argument(currentContour.length === 0, "There are still points left in the current contour.");
        return contours;
      }
      function getPath(points) {
        var p = new Path();
        if (!points) {
          return p;
        }
        var contours = getContours(points);
        for (var contourIndex = 0; contourIndex < contours.length; ++contourIndex) {
          var contour = contours[contourIndex];
          var prev = null;
          var curr = contour[contour.length - 1];
          var next = contour[0];
          if (curr.onCurve) {
            p.moveTo(curr.x, curr.y);
          } else {
            if (next.onCurve) {
              p.moveTo(next.x, next.y);
            } else {
              var start = { x: (curr.x + next.x) * 0.5, y: (curr.y + next.y) * 0.5 };
              p.moveTo(start.x, start.y);
            }
          }
          for (var i = 0; i < contour.length; ++i) {
            prev = curr;
            curr = next;
            next = contour[(i + 1) % contour.length];
            if (curr.onCurve) {
              p.lineTo(curr.x, curr.y);
            } else {
              var prev2 = prev;
              var next2 = next;
              if (!prev.onCurve) {
                prev2 = { x: (curr.x + prev.x) * 0.5, y: (curr.y + prev.y) * 0.5 };
              }
              if (!next.onCurve) {
                next2 = { x: (curr.x + next.x) * 0.5, y: (curr.y + next.y) * 0.5 };
              }
              p.quadraticCurveTo(curr.x, curr.y, next2.x, next2.y);
            }
          }
          p.closePath();
        }
        return p;
      }
      function buildPath(glyphs, glyph) {
        if (glyph.isComposite) {
          for (var j = 0; j < glyph.components.length; j += 1) {
            var component = glyph.components[j];
            var componentGlyph = glyphs.get(component.glyphIndex);
            componentGlyph.getPath();
            if (componentGlyph.points) {
              var transformedPoints = void 0;
              if (component.matchedPoints === void 0) {
                transformedPoints = transformPoints(componentGlyph.points, component);
              } else {
                if (component.matchedPoints[0] > glyph.points.length - 1 || component.matchedPoints[1] > componentGlyph.points.length - 1) {
                  throw Error("Matched points out of range in " + glyph.name);
                }
                var firstPt = glyph.points[component.matchedPoints[0]];
                var secondPt = componentGlyph.points[component.matchedPoints[1]];
                var transform = {
                  xScale: component.xScale,
                  scale01: component.scale01,
                  scale10: component.scale10,
                  yScale: component.yScale,
                  dx: 0,
                  dy: 0
                };
                secondPt = transformPoints([secondPt], transform)[0];
                transform.dx = firstPt.x - secondPt.x;
                transform.dy = firstPt.y - secondPt.y;
                transformedPoints = transformPoints(componentGlyph.points, transform);
              }
              glyph.points = glyph.points.concat(transformedPoints);
            }
          }
        }
        return getPath(glyph.points);
      }
      function parseGlyfTableAll(data, start, loca2, font) {
        var glyphs = new glyphset.GlyphSet(font);
        for (var i = 0; i < loca2.length - 1; i += 1) {
          var offset = loca2[i];
          var nextOffset = loca2[i + 1];
          if (offset !== nextOffset) {
            glyphs.push(i, glyphset.ttfGlyphLoader(font, i, parseGlyph, data, start + offset, buildPath));
          } else {
            glyphs.push(i, glyphset.glyphLoader(font, i));
          }
        }
        return glyphs;
      }
      function parseGlyfTableOnLowMemory(data, start, loca2, font) {
        var glyphs = new glyphset.GlyphSet(font);
        font._push = function(i) {
          var offset = loca2[i];
          var nextOffset = loca2[i + 1];
          if (offset !== nextOffset) {
            glyphs.push(i, glyphset.ttfGlyphLoader(font, i, parseGlyph, data, start + offset, buildPath));
          } else {
            glyphs.push(i, glyphset.glyphLoader(font, i));
          }
        };
        return glyphs;
      }
      function parseGlyfTable(data, start, loca2, font, opt) {
        if (opt.lowMemory) {
          return parseGlyfTableOnLowMemory(data, start, loca2, font);
        } else {
          return parseGlyfTableAll(data, start, loca2, font);
        }
      }
      var glyf = { getPath, parse: parseGlyfTable };
      var instructionTable;
      var exec;
      var execGlyph;
      var execComponent;
      function Hinting(font) {
        this.font = font;
        this.getCommands = function(hPoints) {
          return glyf.getPath(hPoints).commands;
        };
        this._fpgmState = this._prepState = void 0;
        this._errorState = 0;
      }
      function roundOff(v) {
        return v;
      }
      function roundToGrid(v) {
        return Math.sign(v) * Math.round(Math.abs(v));
      }
      function roundToDoubleGrid(v) {
        return Math.sign(v) * Math.round(Math.abs(v * 2)) / 2;
      }
      function roundToHalfGrid(v) {
        return Math.sign(v) * (Math.round(Math.abs(v) + 0.5) - 0.5);
      }
      function roundUpToGrid(v) {
        return Math.sign(v) * Math.ceil(Math.abs(v));
      }
      function roundDownToGrid(v) {
        return Math.sign(v) * Math.floor(Math.abs(v));
      }
      var roundSuper = function(v) {
        var period = this.srPeriod;
        var phase = this.srPhase;
        var threshold = this.srThreshold;
        var sign = 1;
        if (v < 0) {
          v = -v;
          sign = -1;
        }
        v += threshold - phase;
        v = Math.trunc(v / period) * period;
        v += phase;
        if (v < 0) {
          return phase * sign;
        }
        return v * sign;
      };
      var xUnitVector = {
        x: 1,
        y: 0,
        axis: "x",
        // Gets the projected distance between two points.
        // o1/o2 ... if true, respective original position is used.
        distance: function(p1, p2, o1, o2) {
          return (o1 ? p1.xo : p1.x) - (o2 ? p2.xo : p2.x);
        },
        // Moves point p so the moved position has the same relative
        // position to the moved positions of rp1 and rp2 than the
        // original positions had.
        //
        // See APPENDIX on INTERPOLATE at the bottom of this file.
        interpolate: function(p, rp1, rp2, pv) {
          var do1;
          var do2;
          var doa1;
          var doa2;
          var dm1;
          var dm2;
          var dt;
          if (!pv || pv === this) {
            do1 = p.xo - rp1.xo;
            do2 = p.xo - rp2.xo;
            dm1 = rp1.x - rp1.xo;
            dm2 = rp2.x - rp2.xo;
            doa1 = Math.abs(do1);
            doa2 = Math.abs(do2);
            dt = doa1 + doa2;
            if (dt === 0) {
              p.x = p.xo + (dm1 + dm2) / 2;
              return;
            }
            p.x = p.xo + (dm1 * doa2 + dm2 * doa1) / dt;
            return;
          }
          do1 = pv.distance(p, rp1, true, true);
          do2 = pv.distance(p, rp2, true, true);
          dm1 = pv.distance(rp1, rp1, false, true);
          dm2 = pv.distance(rp2, rp2, false, true);
          doa1 = Math.abs(do1);
          doa2 = Math.abs(do2);
          dt = doa1 + doa2;
          if (dt === 0) {
            xUnitVector.setRelative(p, p, (dm1 + dm2) / 2, pv, true);
            return;
          }
          xUnitVector.setRelative(p, p, (dm1 * doa2 + dm2 * doa1) / dt, pv, true);
        },
        // Slope of line normal to this
        normalSlope: Number.NEGATIVE_INFINITY,
        // Sets the point 'p' relative to point 'rp'
        // by the distance 'd'.
        //
        // See APPENDIX on SETRELATIVE at the bottom of this file.
        //
        // p   ... point to set
        // rp  ... reference point
        // d   ... distance on projection vector
        // pv  ... projection vector (undefined = this)
        // org ... if true, uses the original position of rp as reference.
        setRelative: function(p, rp, d, pv, org) {
          if (!pv || pv === this) {
            p.x = (org ? rp.xo : rp.x) + d;
            return;
          }
          var rpx = org ? rp.xo : rp.x;
          var rpy = org ? rp.yo : rp.y;
          var rpdx = rpx + d * pv.x;
          var rpdy = rpy + d * pv.y;
          p.x = rpdx + (p.y - rpdy) / pv.normalSlope;
        },
        // Slope of vector line.
        slope: 0,
        // Touches the point p.
        touch: function(p) {
          p.xTouched = true;
        },
        // Tests if a point p is touched.
        touched: function(p) {
          return p.xTouched;
        },
        // Untouches the point p.
        untouch: function(p) {
          p.xTouched = false;
        }
      };
      var yUnitVector = {
        x: 0,
        y: 1,
        axis: "y",
        // Gets the projected distance between two points.
        // o1/o2 ... if true, respective original position is used.
        distance: function(p1, p2, o1, o2) {
          return (o1 ? p1.yo : p1.y) - (o2 ? p2.yo : p2.y);
        },
        // Moves point p so the moved position has the same relative
        // position to the moved positions of rp1 and rp2 than the
        // original positions had.
        //
        // See APPENDIX on INTERPOLATE at the bottom of this file.
        interpolate: function(p, rp1, rp2, pv) {
          var do1;
          var do2;
          var doa1;
          var doa2;
          var dm1;
          var dm2;
          var dt;
          if (!pv || pv === this) {
            do1 = p.yo - rp1.yo;
            do2 = p.yo - rp2.yo;
            dm1 = rp1.y - rp1.yo;
            dm2 = rp2.y - rp2.yo;
            doa1 = Math.abs(do1);
            doa2 = Math.abs(do2);
            dt = doa1 + doa2;
            if (dt === 0) {
              p.y = p.yo + (dm1 + dm2) / 2;
              return;
            }
            p.y = p.yo + (dm1 * doa2 + dm2 * doa1) / dt;
            return;
          }
          do1 = pv.distance(p, rp1, true, true);
          do2 = pv.distance(p, rp2, true, true);
          dm1 = pv.distance(rp1, rp1, false, true);
          dm2 = pv.distance(rp2, rp2, false, true);
          doa1 = Math.abs(do1);
          doa2 = Math.abs(do2);
          dt = doa1 + doa2;
          if (dt === 0) {
            yUnitVector.setRelative(p, p, (dm1 + dm2) / 2, pv, true);
            return;
          }
          yUnitVector.setRelative(p, p, (dm1 * doa2 + dm2 * doa1) / dt, pv, true);
        },
        // Slope of line normal to this.
        normalSlope: 0,
        // Sets the point 'p' relative to point 'rp'
        // by the distance 'd'
        //
        // See APPENDIX on SETRELATIVE at the bottom of this file.
        //
        // p   ... point to set
        // rp  ... reference point
        // d   ... distance on projection vector
        // pv  ... projection vector (undefined = this)
        // org ... if true, uses the original position of rp as reference.
        setRelative: function(p, rp, d, pv, org) {
          if (!pv || pv === this) {
            p.y = (org ? rp.yo : rp.y) + d;
            return;
          }
          var rpx = org ? rp.xo : rp.x;
          var rpy = org ? rp.yo : rp.y;
          var rpdx = rpx + d * pv.x;
          var rpdy = rpy + d * pv.y;
          p.y = rpdy + pv.normalSlope * (p.x - rpdx);
        },
        // Slope of vector line.
        slope: Number.POSITIVE_INFINITY,
        // Touches the point p.
        touch: function(p) {
          p.yTouched = true;
        },
        // Tests if a point p is touched.
        touched: function(p) {
          return p.yTouched;
        },
        // Untouches the point p.
        untouch: function(p) {
          p.yTouched = false;
        }
      };
      Object.freeze(xUnitVector);
      Object.freeze(yUnitVector);
      function UnitVector(x, y) {
        this.x = x;
        this.y = y;
        this.axis = void 0;
        this.slope = y / x;
        this.normalSlope = -x / y;
        Object.freeze(this);
      }
      UnitVector.prototype.distance = function(p1, p2, o1, o2) {
        return this.x * xUnitVector.distance(p1, p2, o1, o2) + this.y * yUnitVector.distance(p1, p2, o1, o2);
      };
      UnitVector.prototype.interpolate = function(p, rp1, rp2, pv) {
        var dm1;
        var dm2;
        var do1;
        var do2;
        var doa1;
        var doa2;
        var dt;
        do1 = pv.distance(p, rp1, true, true);
        do2 = pv.distance(p, rp2, true, true);
        dm1 = pv.distance(rp1, rp1, false, true);
        dm2 = pv.distance(rp2, rp2, false, true);
        doa1 = Math.abs(do1);
        doa2 = Math.abs(do2);
        dt = doa1 + doa2;
        if (dt === 0) {
          this.setRelative(p, p, (dm1 + dm2) / 2, pv, true);
          return;
        }
        this.setRelative(p, p, (dm1 * doa2 + dm2 * doa1) / dt, pv, true);
      };
      UnitVector.prototype.setRelative = function(p, rp, d, pv, org) {
        pv = pv || this;
        var rpx = org ? rp.xo : rp.x;
        var rpy = org ? rp.yo : rp.y;
        var rpdx = rpx + d * pv.x;
        var rpdy = rpy + d * pv.y;
        var pvns = pv.normalSlope;
        var fvs = this.slope;
        var px = p.x;
        var py = p.y;
        p.x = (fvs * px - pvns * rpdx + rpdy - py) / (fvs - pvns);
        p.y = fvs * (p.x - px) + py;
      };
      UnitVector.prototype.touch = function(p) {
        p.xTouched = true;
        p.yTouched = true;
      };
      function getUnitVector(x, y) {
        var d = Math.sqrt(x * x + y * y);
        x /= d;
        y /= d;
        if (x === 1 && y === 0) {
          return xUnitVector;
        } else if (x === 0 && y === 1) {
          return yUnitVector;
        } else {
          return new UnitVector(x, y);
        }
      }
      function HPoint(x, y, lastPointOfContour, onCurve) {
        this.x = this.xo = Math.round(x * 64) / 64;
        this.y = this.yo = Math.round(y * 64) / 64;
        this.lastPointOfContour = lastPointOfContour;
        this.onCurve = onCurve;
        this.prevPointOnContour = void 0;
        this.nextPointOnContour = void 0;
        this.xTouched = false;
        this.yTouched = false;
        Object.preventExtensions(this);
      }
      HPoint.prototype.nextTouched = function(v) {
        var p = this.nextPointOnContour;
        while (!v.touched(p) && p !== this) {
          p = p.nextPointOnContour;
        }
        return p;
      };
      HPoint.prototype.prevTouched = function(v) {
        var p = this.prevPointOnContour;
        while (!v.touched(p) && p !== this) {
          p = p.prevPointOnContour;
        }
        return p;
      };
      var HPZero = Object.freeze(new HPoint(0, 0));
      var defaultState = {
        cvCutIn: 17 / 16,
        // control value cut in
        deltaBase: 9,
        deltaShift: 0.125,
        loop: 1,
        // loops some instructions
        minDis: 1,
        // minimum distance
        autoFlip: true
      };
      function State(env2, prog) {
        this.env = env2;
        this.stack = [];
        this.prog = prog;
        switch (env2) {
          case "glyf":
            this.zp0 = this.zp1 = this.zp2 = 1;
            this.rp0 = this.rp1 = this.rp2 = 0;
          /* fall through */
          case "prep":
            this.fv = this.pv = this.dpv = xUnitVector;
            this.round = roundToGrid;
        }
      }
      Hinting.prototype.exec = function(glyph, ppem) {
        if (typeof ppem !== "number") {
          throw new Error("Point size is not a number!");
        }
        if (this._errorState > 2) {
          return;
        }
        var font = this.font;
        var prepState = this._prepState;
        if (!prepState || prepState.ppem !== ppem) {
          var fpgmState = this._fpgmState;
          if (!fpgmState) {
            State.prototype = defaultState;
            fpgmState = this._fpgmState = new State("fpgm", font.tables.fpgm);
            fpgmState.funcs = [];
            fpgmState.font = font;
            if (exports2.DEBUG) {
              console.log("---EXEC FPGM---");
              fpgmState.step = -1;
            }
            try {
              exec(fpgmState);
            } catch (e) {
              console.log("Hinting error in FPGM:" + e);
              this._errorState = 3;
              return;
            }
          }
          State.prototype = fpgmState;
          prepState = this._prepState = new State("prep", font.tables.prep);
          prepState.ppem = ppem;
          var oCvt = font.tables.cvt;
          if (oCvt) {
            var cvt = prepState.cvt = new Array(oCvt.length);
            var scale = ppem / font.unitsPerEm;
            for (var c = 0; c < oCvt.length; c++) {
              cvt[c] = oCvt[c] * scale;
            }
          } else {
            prepState.cvt = [];
          }
          if (exports2.DEBUG) {
            console.log("---EXEC PREP---");
            prepState.step = -1;
          }
          try {
            exec(prepState);
          } catch (e) {
            if (this._errorState < 2) {
              console.log("Hinting error in PREP:" + e);
            }
            this._errorState = 2;
          }
        }
        if (this._errorState > 1) {
          return;
        }
        try {
          return execGlyph(glyph, prepState);
        } catch (e) {
          if (this._errorState < 1) {
            console.log("Hinting error:" + e);
            console.log("Note: further hinting errors are silenced");
          }
          this._errorState = 1;
          return void 0;
        }
      };
      execGlyph = function(glyph, prepState) {
        var xScale = prepState.ppem / prepState.font.unitsPerEm;
        var yScale = xScale;
        var components = glyph.components;
        var contours;
        var gZone;
        var state2;
        State.prototype = prepState;
        if (!components) {
          state2 = new State("glyf", glyph.instructions);
          if (exports2.DEBUG) {
            console.log("---EXEC GLYPH---");
            state2.step = -1;
          }
          execComponent(glyph, state2, xScale, yScale);
          gZone = state2.gZone;
        } else {
          var font = prepState.font;
          gZone = [];
          contours = [];
          for (var i = 0; i < components.length; i++) {
            var c = components[i];
            var cg = font.glyphs.get(c.glyphIndex);
            state2 = new State("glyf", cg.instructions);
            if (exports2.DEBUG) {
              console.log("---EXEC COMP " + i + "---");
              state2.step = -1;
            }
            execComponent(cg, state2, xScale, yScale);
            var dx = Math.round(c.dx * xScale);
            var dy = Math.round(c.dy * yScale);
            var gz = state2.gZone;
            var cc = state2.contours;
            for (var pi = 0; pi < gz.length; pi++) {
              var p = gz[pi];
              p.xTouched = p.yTouched = false;
              p.xo = p.x = p.x + dx;
              p.yo = p.y = p.y + dy;
            }
            var gLen = gZone.length;
            gZone.push.apply(gZone, gz);
            for (var j = 0; j < cc.length; j++) {
              contours.push(cc[j] + gLen);
            }
          }
          if (glyph.instructions && !state2.inhibitGridFit) {
            state2 = new State("glyf", glyph.instructions);
            state2.gZone = state2.z0 = state2.z1 = state2.z2 = gZone;
            state2.contours = contours;
            gZone.push(
              new HPoint(0, 0),
              new HPoint(Math.round(glyph.advanceWidth * xScale), 0)
            );
            if (exports2.DEBUG) {
              console.log("---EXEC COMPOSITE---");
              state2.step = -1;
            }
            exec(state2);
            gZone.length -= 2;
          }
        }
        return gZone;
      };
      execComponent = function(glyph, state2, xScale, yScale) {
        var points = glyph.points || [];
        var pLen = points.length;
        var gZone = state2.gZone = state2.z0 = state2.z1 = state2.z2 = [];
        var contours = state2.contours = [];
        var cp;
        for (var i = 0; i < pLen; i++) {
          cp = points[i];
          gZone[i] = new HPoint(
            cp.x * xScale,
            cp.y * yScale,
            cp.lastPointOfContour,
            cp.onCurve
          );
        }
        var sp;
        var np;
        for (var i$1 = 0; i$1 < pLen; i$1++) {
          cp = gZone[i$1];
          if (!sp) {
            sp = cp;
            contours.push(i$1);
          }
          if (cp.lastPointOfContour) {
            cp.nextPointOnContour = sp;
            sp.prevPointOnContour = cp;
            sp = void 0;
          } else {
            np = gZone[i$1 + 1];
            cp.nextPointOnContour = np;
            np.prevPointOnContour = cp;
          }
        }
        if (state2.inhibitGridFit) {
          return;
        }
        if (exports2.DEBUG) {
          console.log("PROCESSING GLYPH", state2.stack);
          for (var i$2 = 0; i$2 < pLen; i$2++) {
            console.log(i$2, gZone[i$2].x, gZone[i$2].y);
          }
        }
        gZone.push(
          new HPoint(0, 0),
          new HPoint(Math.round(glyph.advanceWidth * xScale), 0)
        );
        exec(state2);
        gZone.length -= 2;
        if (exports2.DEBUG) {
          console.log("FINISHED GLYPH", state2.stack);
          for (var i$3 = 0; i$3 < pLen; i$3++) {
            console.log(i$3, gZone[i$3].x, gZone[i$3].y);
          }
        }
      };
      exec = function(state2) {
        var prog = state2.prog;
        if (!prog) {
          return;
        }
        var pLen = prog.length;
        var ins;
        for (state2.ip = 0; state2.ip < pLen; state2.ip++) {
          if (exports2.DEBUG) {
            state2.step++;
          }
          ins = instructionTable[prog[state2.ip]];
          if (!ins) {
            throw new Error(
              "unknown instruction: 0x" + Number(prog[state2.ip]).toString(16)
            );
          }
          ins(state2);
        }
      };
      function initTZone(state2) {
        var tZone = state2.tZone = new Array(state2.gZone.length);
        for (var i = 0; i < tZone.length; i++) {
          tZone[i] = new HPoint(0, 0);
        }
      }
      function skip(state2, handleElse) {
        var prog = state2.prog;
        var ip = state2.ip;
        var nesting = 1;
        var ins;
        do {
          ins = prog[++ip];
          if (ins === 88) {
            nesting++;
          } else if (ins === 89) {
            nesting--;
          } else if (ins === 64) {
            ip += prog[ip + 1] + 1;
          } else if (ins === 65) {
            ip += 2 * prog[ip + 1] + 1;
          } else if (ins >= 176 && ins <= 183) {
            ip += ins - 176 + 1;
          } else if (ins >= 184 && ins <= 191) {
            ip += (ins - 184 + 1) * 2;
          } else if (handleElse && nesting === 1 && ins === 27) {
            break;
          }
        } while (nesting > 0);
        state2.ip = ip;
      }
      function SVTCA(v, state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "SVTCA[" + v.axis + "]");
        }
        state2.fv = state2.pv = state2.dpv = v;
      }
      function SPVTCA(v, state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "SPVTCA[" + v.axis + "]");
        }
        state2.pv = state2.dpv = v;
      }
      function SFVTCA(v, state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "SFVTCA[" + v.axis + "]");
        }
        state2.fv = v;
      }
      function SPVTL(a, state2) {
        var stack = state2.stack;
        var p2i = stack.pop();
        var p1i = stack.pop();
        var p2 = state2.z2[p2i];
        var p1 = state2.z1[p1i];
        if (exports2.DEBUG) {
          console.log("SPVTL[" + a + "]", p2i, p1i);
        }
        var dx;
        var dy;
        if (!a) {
          dx = p1.x - p2.x;
          dy = p1.y - p2.y;
        } else {
          dx = p2.y - p1.y;
          dy = p1.x - p2.x;
        }
        state2.pv = state2.dpv = getUnitVector(dx, dy);
      }
      function SFVTL(a, state2) {
        var stack = state2.stack;
        var p2i = stack.pop();
        var p1i = stack.pop();
        var p2 = state2.z2[p2i];
        var p1 = state2.z1[p1i];
        if (exports2.DEBUG) {
          console.log("SFVTL[" + a + "]", p2i, p1i);
        }
        var dx;
        var dy;
        if (!a) {
          dx = p1.x - p2.x;
          dy = p1.y - p2.y;
        } else {
          dx = p2.y - p1.y;
          dy = p1.x - p2.x;
        }
        state2.fv = getUnitVector(dx, dy);
      }
      function SPVFS(state2) {
        var stack = state2.stack;
        var y = stack.pop();
        var x = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SPVFS[]", y, x);
        }
        state2.pv = state2.dpv = getUnitVector(x, y);
      }
      function SFVFS(state2) {
        var stack = state2.stack;
        var y = stack.pop();
        var x = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SPVFS[]", y, x);
        }
        state2.fv = getUnitVector(x, y);
      }
      function GPV(state2) {
        var stack = state2.stack;
        var pv = state2.pv;
        if (exports2.DEBUG) {
          console.log(state2.step, "GPV[]");
        }
        stack.push(pv.x * 16384);
        stack.push(pv.y * 16384);
      }
      function GFV(state2) {
        var stack = state2.stack;
        var fv = state2.fv;
        if (exports2.DEBUG) {
          console.log(state2.step, "GFV[]");
        }
        stack.push(fv.x * 16384);
        stack.push(fv.y * 16384);
      }
      function SFVTPV(state2) {
        state2.fv = state2.pv;
        if (exports2.DEBUG) {
          console.log(state2.step, "SFVTPV[]");
        }
      }
      function ISECT(state2) {
        var stack = state2.stack;
        var pa0i = stack.pop();
        var pa1i = stack.pop();
        var pb0i = stack.pop();
        var pb1i = stack.pop();
        var pi = stack.pop();
        var z0 = state2.z0;
        var z1 = state2.z1;
        var pa0 = z0[pa0i];
        var pa1 = z0[pa1i];
        var pb0 = z1[pb0i];
        var pb1 = z1[pb1i];
        var p = state2.z2[pi];
        if (exports2.DEBUG) {
          console.log("ISECT[], ", pa0i, pa1i, pb0i, pb1i, pi);
        }
        var x1 = pa0.x;
        var y1 = pa0.y;
        var x2 = pa1.x;
        var y2 = pa1.y;
        var x3 = pb0.x;
        var y3 = pb0.y;
        var x4 = pb1.x;
        var y4 = pb1.y;
        var div = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4);
        var f1 = x1 * y2 - y1 * x2;
        var f2 = x3 * y4 - y3 * x4;
        p.x = (f1 * (x3 - x4) - f2 * (x1 - x2)) / div;
        p.y = (f1 * (y3 - y4) - f2 * (y1 - y2)) / div;
      }
      function SRP0(state2) {
        state2.rp0 = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SRP0[]", state2.rp0);
        }
      }
      function SRP1(state2) {
        state2.rp1 = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SRP1[]", state2.rp1);
        }
      }
      function SRP2(state2) {
        state2.rp2 = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SRP2[]", state2.rp2);
        }
      }
      function SZP0(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SZP0[]", n);
        }
        state2.zp0 = n;
        switch (n) {
          case 0:
            if (!state2.tZone) {
              initTZone(state2);
            }
            state2.z0 = state2.tZone;
            break;
          case 1:
            state2.z0 = state2.gZone;
            break;
          default:
            throw new Error("Invalid zone pointer");
        }
      }
      function SZP1(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SZP1[]", n);
        }
        state2.zp1 = n;
        switch (n) {
          case 0:
            if (!state2.tZone) {
              initTZone(state2);
            }
            state2.z1 = state2.tZone;
            break;
          case 1:
            state2.z1 = state2.gZone;
            break;
          default:
            throw new Error("Invalid zone pointer");
        }
      }
      function SZP2(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SZP2[]", n);
        }
        state2.zp2 = n;
        switch (n) {
          case 0:
            if (!state2.tZone) {
              initTZone(state2);
            }
            state2.z2 = state2.tZone;
            break;
          case 1:
            state2.z2 = state2.gZone;
            break;
          default:
            throw new Error("Invalid zone pointer");
        }
      }
      function SZPS(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SZPS[]", n);
        }
        state2.zp0 = state2.zp1 = state2.zp2 = n;
        switch (n) {
          case 0:
            if (!state2.tZone) {
              initTZone(state2);
            }
            state2.z0 = state2.z1 = state2.z2 = state2.tZone;
            break;
          case 1:
            state2.z0 = state2.z1 = state2.z2 = state2.gZone;
            break;
          default:
            throw new Error("Invalid zone pointer");
        }
      }
      function SLOOP(state2) {
        state2.loop = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SLOOP[]", state2.loop);
        }
      }
      function RTG(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "RTG[]");
        }
        state2.round = roundToGrid;
      }
      function RTHG(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "RTHG[]");
        }
        state2.round = roundToHalfGrid;
      }
      function SMD(state2) {
        var d = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SMD[]", d);
        }
        state2.minDis = d / 64;
      }
      function ELSE(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "ELSE[]");
        }
        skip(state2, false);
      }
      function JMPR(state2) {
        var o = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "JMPR[]", o);
        }
        state2.ip += o - 1;
      }
      function SCVTCI(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SCVTCI[]", n);
        }
        state2.cvCutIn = n / 64;
      }
      function DUP(state2) {
        var stack = state2.stack;
        if (exports2.DEBUG) {
          console.log(state2.step, "DUP[]");
        }
        stack.push(stack[stack.length - 1]);
      }
      function POP(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "POP[]");
        }
        state2.stack.pop();
      }
      function CLEAR(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "CLEAR[]");
        }
        state2.stack.length = 0;
      }
      function SWAP(state2) {
        var stack = state2.stack;
        var a = stack.pop();
        var b2 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SWAP[]");
        }
        stack.push(a);
        stack.push(b2);
      }
      function DEPTH(state2) {
        var stack = state2.stack;
        if (exports2.DEBUG) {
          console.log(state2.step, "DEPTH[]");
        }
        stack.push(stack.length);
      }
      function LOOPCALL(state2) {
        var stack = state2.stack;
        var fn = stack.pop();
        var c = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "LOOPCALL[]", fn, c);
        }
        var cip = state2.ip;
        var cprog = state2.prog;
        state2.prog = state2.funcs[fn];
        for (var i = 0; i < c; i++) {
          exec(state2);
          if (exports2.DEBUG) {
            console.log(
              ++state2.step,
              i + 1 < c ? "next loopcall" : "done loopcall",
              i
            );
          }
        }
        state2.ip = cip;
        state2.prog = cprog;
      }
      function CALL(state2) {
        var fn = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "CALL[]", fn);
        }
        var cip = state2.ip;
        var cprog = state2.prog;
        state2.prog = state2.funcs[fn];
        exec(state2);
        state2.ip = cip;
        state2.prog = cprog;
        if (exports2.DEBUG) {
          console.log(++state2.step, "returning from", fn);
        }
      }
      function CINDEX(state2) {
        var stack = state2.stack;
        var k = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "CINDEX[]", k);
        }
        stack.push(stack[stack.length - k]);
      }
      function MINDEX(state2) {
        var stack = state2.stack;
        var k = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "MINDEX[]", k);
        }
        stack.push(stack.splice(stack.length - k, 1)[0]);
      }
      function FDEF(state2) {
        if (state2.env !== "fpgm") {
          throw new Error("FDEF not allowed here");
        }
        var stack = state2.stack;
        var prog = state2.prog;
        var ip = state2.ip;
        var fn = stack.pop();
        var ipBegin = ip;
        if (exports2.DEBUG) {
          console.log(state2.step, "FDEF[]", fn);
        }
        while (prog[++ip] !== 45) {
        }
        state2.ip = ip;
        state2.funcs[fn] = prog.slice(ipBegin + 1, ip);
      }
      function MDAP(round, state2) {
        var pi = state2.stack.pop();
        var p = state2.z0[pi];
        var fv = state2.fv;
        var pv = state2.pv;
        if (exports2.DEBUG) {
          console.log(state2.step, "MDAP[" + round + "]", pi);
        }
        var d = pv.distance(p, HPZero);
        if (round) {
          d = state2.round(d);
        }
        fv.setRelative(p, HPZero, d, pv);
        fv.touch(p);
        state2.rp0 = state2.rp1 = pi;
      }
      function IUP(v, state2) {
        var z2 = state2.z2;
        var pLen = z2.length - 2;
        var cp;
        var pp;
        var np;
        if (exports2.DEBUG) {
          console.log(state2.step, "IUP[" + v.axis + "]");
        }
        for (var i = 0; i < pLen; i++) {
          cp = z2[i];
          if (v.touched(cp)) {
            continue;
          }
          pp = cp.prevTouched(v);
          if (pp === cp) {
            continue;
          }
          np = cp.nextTouched(v);
          if (pp === np) {
            v.setRelative(cp, cp, v.distance(pp, pp, false, true), v, true);
          }
          v.interpolate(cp, pp, np, v);
        }
      }
      function SHP(a, state2) {
        var stack = state2.stack;
        var rpi = a ? state2.rp1 : state2.rp2;
        var rp = (a ? state2.z0 : state2.z1)[rpi];
        var fv = state2.fv;
        var pv = state2.pv;
        var loop = state2.loop;
        var z2 = state2.z2;
        while (loop--) {
          var pi = stack.pop();
          var p = z2[pi];
          var d = pv.distance(rp, rp, false, true);
          fv.setRelative(p, p, d, pv);
          fv.touch(p);
          if (exports2.DEBUG) {
            console.log(
              state2.step,
              (state2.loop > 1 ? "loop " + (state2.loop - loop) + ": " : "") + "SHP[" + (a ? "rp1" : "rp2") + "]",
              pi
            );
          }
        }
        state2.loop = 1;
      }
      function SHC(a, state2) {
        var stack = state2.stack;
        var rpi = a ? state2.rp1 : state2.rp2;
        var rp = (a ? state2.z0 : state2.z1)[rpi];
        var fv = state2.fv;
        var pv = state2.pv;
        var ci = stack.pop();
        var sp = state2.z2[state2.contours[ci]];
        var p = sp;
        if (exports2.DEBUG) {
          console.log(state2.step, "SHC[" + a + "]", ci);
        }
        var d = pv.distance(rp, rp, false, true);
        do {
          if (p !== rp) {
            fv.setRelative(p, p, d, pv);
          }
          p = p.nextPointOnContour;
        } while (p !== sp);
      }
      function SHZ(a, state2) {
        var stack = state2.stack;
        var rpi = a ? state2.rp1 : state2.rp2;
        var rp = (a ? state2.z0 : state2.z1)[rpi];
        var fv = state2.fv;
        var pv = state2.pv;
        var e = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SHZ[" + a + "]", e);
        }
        var z;
        switch (e) {
          case 0:
            z = state2.tZone;
            break;
          case 1:
            z = state2.gZone;
            break;
          default:
            throw new Error("Invalid zone");
        }
        var p;
        var d = pv.distance(rp, rp, false, true);
        var pLen = z.length - 2;
        for (var i = 0; i < pLen; i++) {
          p = z[i];
          fv.setRelative(p, p, d, pv);
        }
      }
      function SHPIX(state2) {
        var stack = state2.stack;
        var loop = state2.loop;
        var fv = state2.fv;
        var d = stack.pop() / 64;
        var z2 = state2.z2;
        while (loop--) {
          var pi = stack.pop();
          var p = z2[pi];
          if (exports2.DEBUG) {
            console.log(
              state2.step,
              (state2.loop > 1 ? "loop " + (state2.loop - loop) + ": " : "") + "SHPIX[]",
              pi,
              d
            );
          }
          fv.setRelative(p, p, d);
          fv.touch(p);
        }
        state2.loop = 1;
      }
      function IP(state2) {
        var stack = state2.stack;
        var rp1i = state2.rp1;
        var rp2i = state2.rp2;
        var loop = state2.loop;
        var rp1 = state2.z0[rp1i];
        var rp2 = state2.z1[rp2i];
        var fv = state2.fv;
        var pv = state2.dpv;
        var z2 = state2.z2;
        while (loop--) {
          var pi = stack.pop();
          var p = z2[pi];
          if (exports2.DEBUG) {
            console.log(
              state2.step,
              (state2.loop > 1 ? "loop " + (state2.loop - loop) + ": " : "") + "IP[]",
              pi,
              rp1i,
              "<->",
              rp2i
            );
          }
          fv.interpolate(p, rp1, rp2, pv);
          fv.touch(p);
        }
        state2.loop = 1;
      }
      function MSIRP(a, state2) {
        var stack = state2.stack;
        var d = stack.pop() / 64;
        var pi = stack.pop();
        var p = state2.z1[pi];
        var rp0 = state2.z0[state2.rp0];
        var fv = state2.fv;
        var pv = state2.pv;
        fv.setRelative(p, rp0, d, pv);
        fv.touch(p);
        if (exports2.DEBUG) {
          console.log(state2.step, "MSIRP[" + a + "]", d, pi);
        }
        state2.rp1 = state2.rp0;
        state2.rp2 = pi;
        if (a) {
          state2.rp0 = pi;
        }
      }
      function ALIGNRP(state2) {
        var stack = state2.stack;
        var rp0i = state2.rp0;
        var rp0 = state2.z0[rp0i];
        var loop = state2.loop;
        var fv = state2.fv;
        var pv = state2.pv;
        var z1 = state2.z1;
        while (loop--) {
          var pi = stack.pop();
          var p = z1[pi];
          if (exports2.DEBUG) {
            console.log(
              state2.step,
              (state2.loop > 1 ? "loop " + (state2.loop - loop) + ": " : "") + "ALIGNRP[]",
              pi
            );
          }
          fv.setRelative(p, rp0, 0, pv);
          fv.touch(p);
        }
        state2.loop = 1;
      }
      function RTDG(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "RTDG[]");
        }
        state2.round = roundToDoubleGrid;
      }
      function MIAP(round, state2) {
        var stack = state2.stack;
        var n = stack.pop();
        var pi = stack.pop();
        var p = state2.z0[pi];
        var fv = state2.fv;
        var pv = state2.pv;
        var cv = state2.cvt[n];
        if (exports2.DEBUG) {
          console.log(
            state2.step,
            "MIAP[" + round + "]",
            n,
            "(",
            cv,
            ")",
            pi
          );
        }
        var d = pv.distance(p, HPZero);
        if (round) {
          if (Math.abs(d - cv) < state2.cvCutIn) {
            d = cv;
          }
          d = state2.round(d);
        }
        fv.setRelative(p, HPZero, d, pv);
        if (state2.zp0 === 0) {
          p.xo = p.x;
          p.yo = p.y;
        }
        fv.touch(p);
        state2.rp0 = state2.rp1 = pi;
      }
      function NPUSHB(state2) {
        var prog = state2.prog;
        var ip = state2.ip;
        var stack = state2.stack;
        var n = prog[++ip];
        if (exports2.DEBUG) {
          console.log(state2.step, "NPUSHB[]", n);
        }
        for (var i = 0; i < n; i++) {
          stack.push(prog[++ip]);
        }
        state2.ip = ip;
      }
      function NPUSHW(state2) {
        var ip = state2.ip;
        var prog = state2.prog;
        var stack = state2.stack;
        var n = prog[++ip];
        if (exports2.DEBUG) {
          console.log(state2.step, "NPUSHW[]", n);
        }
        for (var i = 0; i < n; i++) {
          var w = prog[++ip] << 8 | prog[++ip];
          if (w & 32768) {
            w = -((w ^ 65535) + 1);
          }
          stack.push(w);
        }
        state2.ip = ip;
      }
      function WS(state2) {
        var stack = state2.stack;
        var store = state2.store;
        if (!store) {
          store = state2.store = [];
        }
        var v = stack.pop();
        var l = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "WS", v, l);
        }
        store[l] = v;
      }
      function RS(state2) {
        var stack = state2.stack;
        var store = state2.store;
        var l = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "RS", l);
        }
        var v = store && store[l] || 0;
        stack.push(v);
      }
      function WCVTP(state2) {
        var stack = state2.stack;
        var v = stack.pop();
        var l = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "WCVTP", v, l);
        }
        state2.cvt[l] = v / 64;
      }
      function RCVT(state2) {
        var stack = state2.stack;
        var cvte = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "RCVT", cvte);
        }
        stack.push(state2.cvt[cvte] * 64);
      }
      function GC(a, state2) {
        var stack = state2.stack;
        var pi = stack.pop();
        var p = state2.z2[pi];
        if (exports2.DEBUG) {
          console.log(state2.step, "GC[" + a + "]", pi);
        }
        stack.push(state2.dpv.distance(p, HPZero, a, false) * 64);
      }
      function MD(a, state2) {
        var stack = state2.stack;
        var pi2 = stack.pop();
        var pi1 = stack.pop();
        var p2 = state2.z1[pi2];
        var p1 = state2.z0[pi1];
        var d = state2.dpv.distance(p1, p2, a, a);
        if (exports2.DEBUG) {
          console.log(state2.step, "MD[" + a + "]", pi2, pi1, "->", d);
        }
        state2.stack.push(Math.round(d * 64));
      }
      function MPPEM(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "MPPEM[]");
        }
        state2.stack.push(state2.ppem);
      }
      function FLIPON(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "FLIPON[]");
        }
        state2.autoFlip = true;
      }
      function LT(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "LT[]", e2, e1);
        }
        stack.push(e1 < e2 ? 1 : 0);
      }
      function LTEQ(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "LTEQ[]", e2, e1);
        }
        stack.push(e1 <= e2 ? 1 : 0);
      }
      function GT(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "GT[]", e2, e1);
        }
        stack.push(e1 > e2 ? 1 : 0);
      }
      function GTEQ(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "GTEQ[]", e2, e1);
        }
        stack.push(e1 >= e2 ? 1 : 0);
      }
      function EQ(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "EQ[]", e2, e1);
        }
        stack.push(e2 === e1 ? 1 : 0);
      }
      function NEQ(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "NEQ[]", e2, e1);
        }
        stack.push(e2 !== e1 ? 1 : 0);
      }
      function ODD(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "ODD[]", n);
        }
        stack.push(Math.trunc(n) % 2 ? 1 : 0);
      }
      function EVEN(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "EVEN[]", n);
        }
        stack.push(Math.trunc(n) % 2 ? 0 : 1);
      }
      function IF(state2) {
        var test = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "IF[]", test);
        }
        if (!test) {
          skip(state2, true);
          if (exports2.DEBUG) {
            console.log(state2.step, "EIF[]");
          }
        }
      }
      function EIF(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "EIF[]");
        }
      }
      function AND(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "AND[]", e2, e1);
        }
        stack.push(e2 && e1 ? 1 : 0);
      }
      function OR(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "OR[]", e2, e1);
        }
        stack.push(e2 || e1 ? 1 : 0);
      }
      function NOT(state2) {
        var stack = state2.stack;
        var e = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "NOT[]", e);
        }
        stack.push(e ? 0 : 1);
      }
      function DELTAP123(b2, state2) {
        var stack = state2.stack;
        var n = stack.pop();
        var fv = state2.fv;
        var pv = state2.pv;
        var ppem = state2.ppem;
        var base = state2.deltaBase + (b2 - 1) * 16;
        var ds = state2.deltaShift;
        var z0 = state2.z0;
        if (exports2.DEBUG) {
          console.log(state2.step, "DELTAP[" + b2 + "]", n, stack);
        }
        for (var i = 0; i < n; i++) {
          var pi = stack.pop();
          var arg = stack.pop();
          var appem = base + ((arg & 240) >> 4);
          if (appem !== ppem) {
            continue;
          }
          var mag = (arg & 15) - 8;
          if (mag >= 0) {
            mag++;
          }
          if (exports2.DEBUG) {
            console.log(state2.step, "DELTAPFIX", pi, "by", mag * ds);
          }
          var p = z0[pi];
          fv.setRelative(p, p, mag * ds, pv);
        }
      }
      function SDB(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SDB[]", n);
        }
        state2.deltaBase = n;
      }
      function SDS(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SDS[]", n);
        }
        state2.deltaShift = Math.pow(0.5, n);
      }
      function ADD(state2) {
        var stack = state2.stack;
        var n2 = stack.pop();
        var n1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "ADD[]", n2, n1);
        }
        stack.push(n1 + n2);
      }
      function SUB(state2) {
        var stack = state2.stack;
        var n2 = stack.pop();
        var n1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SUB[]", n2, n1);
        }
        stack.push(n1 - n2);
      }
      function DIV(state2) {
        var stack = state2.stack;
        var n2 = stack.pop();
        var n1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "DIV[]", n2, n1);
        }
        stack.push(n1 * 64 / n2);
      }
      function MUL(state2) {
        var stack = state2.stack;
        var n2 = stack.pop();
        var n1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "MUL[]", n2, n1);
        }
        stack.push(n1 * n2 / 64);
      }
      function ABS(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "ABS[]", n);
        }
        stack.push(Math.abs(n));
      }
      function NEG(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "NEG[]", n);
        }
        stack.push(-n);
      }
      function FLOOR(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "FLOOR[]", n);
        }
        stack.push(Math.floor(n / 64) * 64);
      }
      function CEILING(state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "CEILING[]", n);
        }
        stack.push(Math.ceil(n / 64) * 64);
      }
      function ROUND(dt, state2) {
        var stack = state2.stack;
        var n = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "ROUND[]");
        }
        stack.push(state2.round(n / 64) * 64);
      }
      function WCVTF(state2) {
        var stack = state2.stack;
        var v = stack.pop();
        var l = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "WCVTF[]", v, l);
        }
        state2.cvt[l] = v * state2.ppem / state2.font.unitsPerEm;
      }
      function DELTAC123(b2, state2) {
        var stack = state2.stack;
        var n = stack.pop();
        var ppem = state2.ppem;
        var base = state2.deltaBase + (b2 - 1) * 16;
        var ds = state2.deltaShift;
        if (exports2.DEBUG) {
          console.log(state2.step, "DELTAC[" + b2 + "]", n, stack);
        }
        for (var i = 0; i < n; i++) {
          var c = stack.pop();
          var arg = stack.pop();
          var appem = base + ((arg & 240) >> 4);
          if (appem !== ppem) {
            continue;
          }
          var mag = (arg & 15) - 8;
          if (mag >= 0) {
            mag++;
          }
          var delta = mag * ds;
          if (exports2.DEBUG) {
            console.log(state2.step, "DELTACFIX", c, "by", delta);
          }
          state2.cvt[c] += delta;
        }
      }
      function SROUND(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SROUND[]", n);
        }
        state2.round = roundSuper;
        var period;
        switch (n & 192) {
          case 0:
            period = 0.5;
            break;
          case 64:
            period = 1;
            break;
          case 128:
            period = 2;
            break;
          default:
            throw new Error("invalid SROUND value");
        }
        state2.srPeriod = period;
        switch (n & 48) {
          case 0:
            state2.srPhase = 0;
            break;
          case 16:
            state2.srPhase = 0.25 * period;
            break;
          case 32:
            state2.srPhase = 0.5 * period;
            break;
          case 48:
            state2.srPhase = 0.75 * period;
            break;
          default:
            throw new Error("invalid SROUND value");
        }
        n &= 15;
        if (n === 0) {
          state2.srThreshold = 0;
        } else {
          state2.srThreshold = (n / 8 - 0.5) * period;
        }
      }
      function S45ROUND(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "S45ROUND[]", n);
        }
        state2.round = roundSuper;
        var period;
        switch (n & 192) {
          case 0:
            period = Math.sqrt(2) / 2;
            break;
          case 64:
            period = Math.sqrt(2);
            break;
          case 128:
            period = 2 * Math.sqrt(2);
            break;
          default:
            throw new Error("invalid S45ROUND value");
        }
        state2.srPeriod = period;
        switch (n & 48) {
          case 0:
            state2.srPhase = 0;
            break;
          case 16:
            state2.srPhase = 0.25 * period;
            break;
          case 32:
            state2.srPhase = 0.5 * period;
            break;
          case 48:
            state2.srPhase = 0.75 * period;
            break;
          default:
            throw new Error("invalid S45ROUND value");
        }
        n &= 15;
        if (n === 0) {
          state2.srThreshold = 0;
        } else {
          state2.srThreshold = (n / 8 - 0.5) * period;
        }
      }
      function ROFF(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "ROFF[]");
        }
        state2.round = roundOff;
      }
      function RUTG(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "RUTG[]");
        }
        state2.round = roundUpToGrid;
      }
      function RDTG(state2) {
        if (exports2.DEBUG) {
          console.log(state2.step, "RDTG[]");
        }
        state2.round = roundDownToGrid;
      }
      function SCANCTRL(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SCANCTRL[]", n);
        }
      }
      function SDPVTL(a, state2) {
        var stack = state2.stack;
        var p2i = stack.pop();
        var p1i = stack.pop();
        var p2 = state2.z2[p2i];
        var p1 = state2.z1[p1i];
        if (exports2.DEBUG) {
          console.log(state2.step, "SDPVTL[" + a + "]", p2i, p1i);
        }
        var dx;
        var dy;
        if (!a) {
          dx = p1.x - p2.x;
          dy = p1.y - p2.y;
        } else {
          dx = p2.y - p1.y;
          dy = p1.x - p2.x;
        }
        state2.dpv = getUnitVector(dx, dy);
      }
      function GETINFO(state2) {
        var stack = state2.stack;
        var sel = stack.pop();
        var r = 0;
        if (exports2.DEBUG) {
          console.log(state2.step, "GETINFO[]", sel);
        }
        if (sel & 1) {
          r = 35;
        }
        if (sel & 32) {
          r |= 4096;
        }
        stack.push(r);
      }
      function ROLL(state2) {
        var stack = state2.stack;
        var a = stack.pop();
        var b2 = stack.pop();
        var c = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "ROLL[]");
        }
        stack.push(b2);
        stack.push(a);
        stack.push(c);
      }
      function MAX(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "MAX[]", e2, e1);
        }
        stack.push(Math.max(e1, e2));
      }
      function MIN(state2) {
        var stack = state2.stack;
        var e2 = stack.pop();
        var e1 = stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "MIN[]", e2, e1);
        }
        stack.push(Math.min(e1, e2));
      }
      function SCANTYPE(state2) {
        var n = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "SCANTYPE[]", n);
        }
      }
      function INSTCTRL(state2) {
        var s = state2.stack.pop();
        var v = state2.stack.pop();
        if (exports2.DEBUG) {
          console.log(state2.step, "INSTCTRL[]", s, v);
        }
        switch (s) {
          case 1:
            state2.inhibitGridFit = !!v;
            return;
          case 2:
            state2.ignoreCvt = !!v;
            return;
          default:
            throw new Error("invalid INSTCTRL[] selector");
        }
      }
      function PUSHB(n, state2) {
        var stack = state2.stack;
        var prog = state2.prog;
        var ip = state2.ip;
        if (exports2.DEBUG) {
          console.log(state2.step, "PUSHB[" + n + "]");
        }
        for (var i = 0; i < n; i++) {
          stack.push(prog[++ip]);
        }
        state2.ip = ip;
      }
      function PUSHW(n, state2) {
        var ip = state2.ip;
        var prog = state2.prog;
        var stack = state2.stack;
        if (exports2.DEBUG) {
          console.log(state2.ip, "PUSHW[" + n + "]");
        }
        for (var i = 0; i < n; i++) {
          var w = prog[++ip] << 8 | prog[++ip];
          if (w & 32768) {
            w = -((w ^ 65535) + 1);
          }
          stack.push(w);
        }
        state2.ip = ip;
      }
      function MDRP_MIRP(indirect, setRp0, keepD, ro, dt, state2) {
        var stack = state2.stack;
        var cvte = indirect && stack.pop();
        var pi = stack.pop();
        var rp0i = state2.rp0;
        var rp = state2.z0[rp0i];
        var p = state2.z1[pi];
        var md = state2.minDis;
        var fv = state2.fv;
        var pv = state2.dpv;
        var od;
        var d;
        var sign;
        var cv;
        d = od = pv.distance(p, rp, true, true);
        sign = d >= 0 ? 1 : -1;
        d = Math.abs(d);
        if (indirect) {
          cv = state2.cvt[cvte];
          if (ro && Math.abs(d - cv) < state2.cvCutIn) {
            d = cv;
          }
        }
        if (keepD && d < md) {
          d = md;
        }
        if (ro) {
          d = state2.round(d);
        }
        fv.setRelative(p, rp, sign * d, pv);
        fv.touch(p);
        if (exports2.DEBUG) {
          console.log(
            state2.step,
            (indirect ? "MIRP[" : "MDRP[") + (setRp0 ? "M" : "m") + (keepD ? ">" : "_") + (ro ? "R" : "_") + (dt === 0 ? "Gr" : dt === 1 ? "Bl" : dt === 2 ? "Wh" : "") + "]",
            indirect ? cvte + "(" + state2.cvt[cvte] + "," + cv + ")" : "",
            pi,
            "(d =",
            od,
            "->",
            sign * d,
            ")"
          );
        }
        state2.rp1 = state2.rp0;
        state2.rp2 = pi;
        if (setRp0) {
          state2.rp0 = pi;
        }
      }
      instructionTable = [
        /* 0x00 */
        SVTCA.bind(void 0, yUnitVector),
        /* 0x01 */
        SVTCA.bind(void 0, xUnitVector),
        /* 0x02 */
        SPVTCA.bind(void 0, yUnitVector),
        /* 0x03 */
        SPVTCA.bind(void 0, xUnitVector),
        /* 0x04 */
        SFVTCA.bind(void 0, yUnitVector),
        /* 0x05 */
        SFVTCA.bind(void 0, xUnitVector),
        /* 0x06 */
        SPVTL.bind(void 0, 0),
        /* 0x07 */
        SPVTL.bind(void 0, 1),
        /* 0x08 */
        SFVTL.bind(void 0, 0),
        /* 0x09 */
        SFVTL.bind(void 0, 1),
        /* 0x0A */
        SPVFS,
        /* 0x0B */
        SFVFS,
        /* 0x0C */
        GPV,
        /* 0x0D */
        GFV,
        /* 0x0E */
        SFVTPV,
        /* 0x0F */
        ISECT,
        /* 0x10 */
        SRP0,
        /* 0x11 */
        SRP1,
        /* 0x12 */
        SRP2,
        /* 0x13 */
        SZP0,
        /* 0x14 */
        SZP1,
        /* 0x15 */
        SZP2,
        /* 0x16 */
        SZPS,
        /* 0x17 */
        SLOOP,
        /* 0x18 */
        RTG,
        /* 0x19 */
        RTHG,
        /* 0x1A */
        SMD,
        /* 0x1B */
        ELSE,
        /* 0x1C */
        JMPR,
        /* 0x1D */
        SCVTCI,
        /* 0x1E */
        void 0,
        // TODO SSWCI
        /* 0x1F */
        void 0,
        // TODO SSW
        /* 0x20 */
        DUP,
        /* 0x21 */
        POP,
        /* 0x22 */
        CLEAR,
        /* 0x23 */
        SWAP,
        /* 0x24 */
        DEPTH,
        /* 0x25 */
        CINDEX,
        /* 0x26 */
        MINDEX,
        /* 0x27 */
        void 0,
        // TODO ALIGNPTS
        /* 0x28 */
        void 0,
        /* 0x29 */
        void 0,
        // TODO UTP
        /* 0x2A */
        LOOPCALL,
        /* 0x2B */
        CALL,
        /* 0x2C */
        FDEF,
        /* 0x2D */
        void 0,
        // ENDF (eaten by FDEF)
        /* 0x2E */
        MDAP.bind(void 0, 0),
        /* 0x2F */
        MDAP.bind(void 0, 1),
        /* 0x30 */
        IUP.bind(void 0, yUnitVector),
        /* 0x31 */
        IUP.bind(void 0, xUnitVector),
        /* 0x32 */
        SHP.bind(void 0, 0),
        /* 0x33 */
        SHP.bind(void 0, 1),
        /* 0x34 */
        SHC.bind(void 0, 0),
        /* 0x35 */
        SHC.bind(void 0, 1),
        /* 0x36 */
        SHZ.bind(void 0, 0),
        /* 0x37 */
        SHZ.bind(void 0, 1),
        /* 0x38 */
        SHPIX,
        /* 0x39 */
        IP,
        /* 0x3A */
        MSIRP.bind(void 0, 0),
        /* 0x3B */
        MSIRP.bind(void 0, 1),
        /* 0x3C */
        ALIGNRP,
        /* 0x3D */
        RTDG,
        /* 0x3E */
        MIAP.bind(void 0, 0),
        /* 0x3F */
        MIAP.bind(void 0, 1),
        /* 0x40 */
        NPUSHB,
        /* 0x41 */
        NPUSHW,
        /* 0x42 */
        WS,
        /* 0x43 */
        RS,
        /* 0x44 */
        WCVTP,
        /* 0x45 */
        RCVT,
        /* 0x46 */
        GC.bind(void 0, 0),
        /* 0x47 */
        GC.bind(void 0, 1),
        /* 0x48 */
        void 0,
        // TODO SCFS
        /* 0x49 */
        MD.bind(void 0, 0),
        /* 0x4A */
        MD.bind(void 0, 1),
        /* 0x4B */
        MPPEM,
        /* 0x4C */
        void 0,
        // TODO MPS
        /* 0x4D */
        FLIPON,
        /* 0x4E */
        void 0,
        // TODO FLIPOFF
        /* 0x4F */
        void 0,
        // TODO DEBUG
        /* 0x50 */
        LT,
        /* 0x51 */
        LTEQ,
        /* 0x52 */
        GT,
        /* 0x53 */
        GTEQ,
        /* 0x54 */
        EQ,
        /* 0x55 */
        NEQ,
        /* 0x56 */
        ODD,
        /* 0x57 */
        EVEN,
        /* 0x58 */
        IF,
        /* 0x59 */
        EIF,
        /* 0x5A */
        AND,
        /* 0x5B */
        OR,
        /* 0x5C */
        NOT,
        /* 0x5D */
        DELTAP123.bind(void 0, 1),
        /* 0x5E */
        SDB,
        /* 0x5F */
        SDS,
        /* 0x60 */
        ADD,
        /* 0x61 */
        SUB,
        /* 0x62 */
        DIV,
        /* 0x63 */
        MUL,
        /* 0x64 */
        ABS,
        /* 0x65 */
        NEG,
        /* 0x66 */
        FLOOR,
        /* 0x67 */
        CEILING,
        /* 0x68 */
        ROUND.bind(void 0, 0),
        /* 0x69 */
        ROUND.bind(void 0, 1),
        /* 0x6A */
        ROUND.bind(void 0, 2),
        /* 0x6B */
        ROUND.bind(void 0, 3),
        /* 0x6C */
        void 0,
        // TODO NROUND[ab]
        /* 0x6D */
        void 0,
        // TODO NROUND[ab]
        /* 0x6E */
        void 0,
        // TODO NROUND[ab]
        /* 0x6F */
        void 0,
        // TODO NROUND[ab]
        /* 0x70 */
        WCVTF,
        /* 0x71 */
        DELTAP123.bind(void 0, 2),
        /* 0x72 */
        DELTAP123.bind(void 0, 3),
        /* 0x73 */
        DELTAC123.bind(void 0, 1),
        /* 0x74 */
        DELTAC123.bind(void 0, 2),
        /* 0x75 */
        DELTAC123.bind(void 0, 3),
        /* 0x76 */
        SROUND,
        /* 0x77 */
        S45ROUND,
        /* 0x78 */
        void 0,
        // TODO JROT[]
        /* 0x79 */
        void 0,
        // TODO JROF[]
        /* 0x7A */
        ROFF,
        /* 0x7B */
        void 0,
        /* 0x7C */
        RUTG,
        /* 0x7D */
        RDTG,
        /* 0x7E */
        POP,
        // actually SANGW, supposed to do only a pop though
        /* 0x7F */
        POP,
        // actually AA, supposed to do only a pop though
        /* 0x80 */
        void 0,
        // TODO FLIPPT
        /* 0x81 */
        void 0,
        // TODO FLIPRGON
        /* 0x82 */
        void 0,
        // TODO FLIPRGOFF
        /* 0x83 */
        void 0,
        /* 0x84 */
        void 0,
        /* 0x85 */
        SCANCTRL,
        /* 0x86 */
        SDPVTL.bind(void 0, 0),
        /* 0x87 */
        SDPVTL.bind(void 0, 1),
        /* 0x88 */
        GETINFO,
        /* 0x89 */
        void 0,
        // TODO IDEF
        /* 0x8A */
        ROLL,
        /* 0x8B */
        MAX,
        /* 0x8C */
        MIN,
        /* 0x8D */
        SCANTYPE,
        /* 0x8E */
        INSTCTRL,
        /* 0x8F */
        void 0,
        /* 0x90 */
        void 0,
        /* 0x91 */
        void 0,
        /* 0x92 */
        void 0,
        /* 0x93 */
        void 0,
        /* 0x94 */
        void 0,
        /* 0x95 */
        void 0,
        /* 0x96 */
        void 0,
        /* 0x97 */
        void 0,
        /* 0x98 */
        void 0,
        /* 0x99 */
        void 0,
        /* 0x9A */
        void 0,
        /* 0x9B */
        void 0,
        /* 0x9C */
        void 0,
        /* 0x9D */
        void 0,
        /* 0x9E */
        void 0,
        /* 0x9F */
        void 0,
        /* 0xA0 */
        void 0,
        /* 0xA1 */
        void 0,
        /* 0xA2 */
        void 0,
        /* 0xA3 */
        void 0,
        /* 0xA4 */
        void 0,
        /* 0xA5 */
        void 0,
        /* 0xA6 */
        void 0,
        /* 0xA7 */
        void 0,
        /* 0xA8 */
        void 0,
        /* 0xA9 */
        void 0,
        /* 0xAA */
        void 0,
        /* 0xAB */
        void 0,
        /* 0xAC */
        void 0,
        /* 0xAD */
        void 0,
        /* 0xAE */
        void 0,
        /* 0xAF */
        void 0,
        /* 0xB0 */
        PUSHB.bind(void 0, 1),
        /* 0xB1 */
        PUSHB.bind(void 0, 2),
        /* 0xB2 */
        PUSHB.bind(void 0, 3),
        /* 0xB3 */
        PUSHB.bind(void 0, 4),
        /* 0xB4 */
        PUSHB.bind(void 0, 5),
        /* 0xB5 */
        PUSHB.bind(void 0, 6),
        /* 0xB6 */
        PUSHB.bind(void 0, 7),
        /* 0xB7 */
        PUSHB.bind(void 0, 8),
        /* 0xB8 */
        PUSHW.bind(void 0, 1),
        /* 0xB9 */
        PUSHW.bind(void 0, 2),
        /* 0xBA */
        PUSHW.bind(void 0, 3),
        /* 0xBB */
        PUSHW.bind(void 0, 4),
        /* 0xBC */
        PUSHW.bind(void 0, 5),
        /* 0xBD */
        PUSHW.bind(void 0, 6),
        /* 0xBE */
        PUSHW.bind(void 0, 7),
        /* 0xBF */
        PUSHW.bind(void 0, 8),
        /* 0xC0 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 0, 0),
        /* 0xC1 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 0, 1),
        /* 0xC2 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 0, 2),
        /* 0xC3 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 0, 3),
        /* 0xC4 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 1, 0),
        /* 0xC5 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 1, 1),
        /* 0xC6 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 1, 2),
        /* 0xC7 */
        MDRP_MIRP.bind(void 0, 0, 0, 0, 1, 3),
        /* 0xC8 */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 0, 0),
        /* 0xC9 */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 0, 1),
        /* 0xCA */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 0, 2),
        /* 0xCB */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 0, 3),
        /* 0xCC */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 1, 0),
        /* 0xCD */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 1, 1),
        /* 0xCE */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 1, 2),
        /* 0xCF */
        MDRP_MIRP.bind(void 0, 0, 0, 1, 1, 3),
        /* 0xD0 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 0, 0),
        /* 0xD1 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 0, 1),
        /* 0xD2 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 0, 2),
        /* 0xD3 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 0, 3),
        /* 0xD4 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 1, 0),
        /* 0xD5 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 1, 1),
        /* 0xD6 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 1, 2),
        /* 0xD7 */
        MDRP_MIRP.bind(void 0, 0, 1, 0, 1, 3),
        /* 0xD8 */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 0, 0),
        /* 0xD9 */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 0, 1),
        /* 0xDA */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 0, 2),
        /* 0xDB */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 0, 3),
        /* 0xDC */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 1, 0),
        /* 0xDD */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 1, 1),
        /* 0xDE */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 1, 2),
        /* 0xDF */
        MDRP_MIRP.bind(void 0, 0, 1, 1, 1, 3),
        /* 0xE0 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 0, 0),
        /* 0xE1 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 0, 1),
        /* 0xE2 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 0, 2),
        /* 0xE3 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 0, 3),
        /* 0xE4 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 1, 0),
        /* 0xE5 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 1, 1),
        /* 0xE6 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 1, 2),
        /* 0xE7 */
        MDRP_MIRP.bind(void 0, 1, 0, 0, 1, 3),
        /* 0xE8 */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 0, 0),
        /* 0xE9 */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 0, 1),
        /* 0xEA */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 0, 2),
        /* 0xEB */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 0, 3),
        /* 0xEC */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 1, 0),
        /* 0xED */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 1, 1),
        /* 0xEE */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 1, 2),
        /* 0xEF */
        MDRP_MIRP.bind(void 0, 1, 0, 1, 1, 3),
        /* 0xF0 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 0, 0),
        /* 0xF1 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 0, 1),
        /* 0xF2 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 0, 2),
        /* 0xF3 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 0, 3),
        /* 0xF4 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 1, 0),
        /* 0xF5 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 1, 1),
        /* 0xF6 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 1, 2),
        /* 0xF7 */
        MDRP_MIRP.bind(void 0, 1, 1, 0, 1, 3),
        /* 0xF8 */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 0, 0),
        /* 0xF9 */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 0, 1),
        /* 0xFA */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 0, 2),
        /* 0xFB */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 0, 3),
        /* 0xFC */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 1, 0),
        /* 0xFD */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 1, 1),
        /* 0xFE */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 1, 2),
        /* 0xFF */
        MDRP_MIRP.bind(void 0, 1, 1, 1, 1, 3)
      ];
      function Token(char) {
        this.char = char;
        this.state = {};
        this.activeState = null;
      }
      function ContextRange(startIndex, endOffset, contextName) {
        this.contextName = contextName;
        this.startIndex = startIndex;
        this.endOffset = endOffset;
      }
      function ContextChecker(contextName, checkStart, checkEnd) {
        this.contextName = contextName;
        this.openRange = null;
        this.ranges = [];
        this.checkStart = checkStart;
        this.checkEnd = checkEnd;
      }
      function ContextParams(context, currentIndex) {
        this.context = context;
        this.index = currentIndex;
        this.length = context.length;
        this.current = context[currentIndex];
        this.backtrack = context.slice(0, currentIndex);
        this.lookahead = context.slice(currentIndex + 1);
      }
      function Event(eventId) {
        this.eventId = eventId;
        this.subscribers = [];
      }
      function initializeCoreEvents(events) {
        var this$1 = this;
        var coreEvents = [
          "start",
          "end",
          "next",
          "newToken",
          "contextStart",
          "contextEnd",
          "insertToken",
          "removeToken",
          "removeRange",
          "replaceToken",
          "replaceRange",
          "composeRUD",
          "updateContextsRanges"
        ];
        coreEvents.forEach(function(eventId) {
          Object.defineProperty(this$1.events, eventId, {
            value: new Event(eventId)
          });
        });
        if (!!events) {
          coreEvents.forEach(function(eventId) {
            var event = events[eventId];
            if (typeof event === "function") {
              this$1.events[eventId].subscribe(event);
            }
          });
        }
        var requiresContextUpdate = [
          "insertToken",
          "removeToken",
          "removeRange",
          "replaceToken",
          "replaceRange",
          "composeRUD"
        ];
        requiresContextUpdate.forEach(function(eventId) {
          this$1.events[eventId].subscribe(
            this$1.updateContextsRanges
          );
        });
      }
      function Tokenizer(events) {
        this.tokens = [];
        this.registeredContexts = {};
        this.contextCheckers = [];
        this.events = {};
        this.registeredModifiers = [];
        initializeCoreEvents.call(this, events);
      }
      Token.prototype.setState = function(key, value) {
        this.state[key] = value;
        this.activeState = { key, value: this.state[key] };
        return this.activeState;
      };
      Token.prototype.getState = function(stateId) {
        return this.state[stateId] || null;
      };
      Tokenizer.prototype.inboundIndex = function(index) {
        return index >= 0 && index < this.tokens.length;
      };
      Tokenizer.prototype.composeRUD = function(RUDs) {
        var this$1 = this;
        var silent = true;
        var state2 = RUDs.map(function(RUD) {
          return this$1[RUD[0]].apply(this$1, RUD.slice(1).concat(silent));
        });
        var hasFAILObject = function(obj) {
          return typeof obj === "object" && obj.hasOwnProperty("FAIL");
        };
        if (state2.every(hasFAILObject)) {
          return {
            FAIL: "composeRUD: one or more operations hasn't completed successfully",
            report: state2.filter(hasFAILObject)
          };
        }
        this.dispatch("composeRUD", [state2.filter(function(op) {
          return !hasFAILObject(op);
        })]);
      };
      Tokenizer.prototype.replaceRange = function(startIndex, offset, tokens, silent) {
        offset = offset !== null ? offset : this.tokens.length;
        var isTokenType = tokens.every(function(token) {
          return token instanceof Token;
        });
        if (!isNaN(startIndex) && this.inboundIndex(startIndex) && isTokenType) {
          var replaced = this.tokens.splice.apply(
            this.tokens,
            [startIndex, offset].concat(tokens)
          );
          if (!silent) {
            this.dispatch("replaceToken", [startIndex, offset, tokens]);
          }
          return [replaced, tokens];
        } else {
          return { FAIL: "replaceRange: invalid tokens or startIndex." };
        }
      };
      Tokenizer.prototype.replaceToken = function(index, token, silent) {
        if (!isNaN(index) && this.inboundIndex(index) && token instanceof Token) {
          var replaced = this.tokens.splice(index, 1, token);
          if (!silent) {
            this.dispatch("replaceToken", [index, token]);
          }
          return [replaced[0], token];
        } else {
          return { FAIL: "replaceToken: invalid token or index." };
        }
      };
      Tokenizer.prototype.removeRange = function(startIndex, offset, silent) {
        offset = !isNaN(offset) ? offset : this.tokens.length;
        var tokens = this.tokens.splice(startIndex, offset);
        if (!silent) {
          this.dispatch("removeRange", [tokens, startIndex, offset]);
        }
        return tokens;
      };
      Tokenizer.prototype.removeToken = function(index, silent) {
        if (!isNaN(index) && this.inboundIndex(index)) {
          var token = this.tokens.splice(index, 1);
          if (!silent) {
            this.dispatch("removeToken", [token, index]);
          }
          return token;
        } else {
          return { FAIL: "removeToken: invalid token index." };
        }
      };
      Tokenizer.prototype.insertToken = function(tokens, index, silent) {
        var tokenType = tokens.every(
          function(token) {
            return token instanceof Token;
          }
        );
        if (tokenType) {
          this.tokens.splice.apply(
            this.tokens,
            [index, 0].concat(tokens)
          );
          if (!silent) {
            this.dispatch("insertToken", [tokens, index]);
          }
          return tokens;
        } else {
          return { FAIL: "insertToken: invalid token(s)." };
        }
      };
      Tokenizer.prototype.registerModifier = function(modifierId, condition, modifier) {
        this.events.newToken.subscribe(function(token, contextParams) {
          var conditionParams = [token, contextParams];
          var canApplyModifier = condition === null || condition.apply(this, conditionParams) === true;
          var modifierParams = [token, contextParams];
          if (canApplyModifier) {
            var newStateValue = modifier.apply(this, modifierParams);
            token.setState(modifierId, newStateValue);
          }
        });
        this.registeredModifiers.push(modifierId);
      };
      Event.prototype.subscribe = function(eventHandler) {
        if (typeof eventHandler === "function") {
          return this.subscribers.push(eventHandler) - 1;
        } else {
          return { FAIL: "invalid '" + this.eventId + "' event handler" };
        }
      };
      Event.prototype.unsubscribe = function(subsId) {
        this.subscribers.splice(subsId, 1);
      };
      ContextParams.prototype.setCurrentIndex = function(index) {
        this.index = index;
        this.current = this.context[index];
        this.backtrack = this.context.slice(0, index);
        this.lookahead = this.context.slice(index + 1);
      };
      ContextParams.prototype.get = function(offset) {
        switch (true) {
          case offset === 0:
            return this.current;
          case (offset < 0 && Math.abs(offset) <= this.backtrack.length):
            return this.backtrack.slice(offset)[0];
          case (offset > 0 && offset <= this.lookahead.length):
            return this.lookahead[offset - 1];
          default:
            return null;
        }
      };
      Tokenizer.prototype.rangeToText = function(range) {
        if (range instanceof ContextRange) {
          return this.getRangeTokens(range).map(function(token) {
            return token.char;
          }).join("");
        }
      };
      Tokenizer.prototype.getText = function() {
        return this.tokens.map(function(token) {
          return token.char;
        }).join("");
      };
      Tokenizer.prototype.getContext = function(contextName) {
        var context = this.registeredContexts[contextName];
        return !!context ? context : null;
      };
      Tokenizer.prototype.on = function(eventName, eventHandler) {
        var event = this.events[eventName];
        if (!!event) {
          return event.subscribe(eventHandler);
        } else {
          return null;
        }
      };
      Tokenizer.prototype.dispatch = function(eventName, args) {
        var this$1 = this;
        var event = this.events[eventName];
        if (event instanceof Event) {
          event.subscribers.forEach(function(subscriber) {
            subscriber.apply(this$1, args || []);
          });
        }
      };
      Tokenizer.prototype.registerContextChecker = function(contextName, contextStartCheck, contextEndCheck) {
        if (!!this.getContext(contextName)) {
          return {
            FAIL: "context name '" + contextName + "' is already registered."
          };
        }
        if (typeof contextStartCheck !== "function") {
          return {
            FAIL: "missing context start check."
          };
        }
        if (typeof contextEndCheck !== "function") {
          return {
            FAIL: "missing context end check."
          };
        }
        var contextCheckers = new ContextChecker(
          contextName,
          contextStartCheck,
          contextEndCheck
        );
        this.registeredContexts[contextName] = contextCheckers;
        this.contextCheckers.push(contextCheckers);
        return contextCheckers;
      };
      Tokenizer.prototype.getRangeTokens = function(range) {
        var endIndex = range.startIndex + range.endOffset;
        return [].concat(
          this.tokens.slice(range.startIndex, endIndex)
        );
      };
      Tokenizer.prototype.getContextRanges = function(contextName) {
        var context = this.getContext(contextName);
        if (!!context) {
          return context.ranges;
        } else {
          return { FAIL: "context checker '" + contextName + "' is not registered." };
        }
      };
      Tokenizer.prototype.resetContextsRanges = function() {
        var registeredContexts = this.registeredContexts;
        for (var contextName in registeredContexts) {
          if (registeredContexts.hasOwnProperty(contextName)) {
            var context = registeredContexts[contextName];
            context.ranges = [];
          }
        }
      };
      Tokenizer.prototype.updateContextsRanges = function() {
        this.resetContextsRanges();
        var chars = this.tokens.map(function(token) {
          return token.char;
        });
        for (var i = 0; i < chars.length; i++) {
          var contextParams = new ContextParams(chars, i);
          this.runContextCheck(contextParams);
        }
        this.dispatch("updateContextsRanges", [this.registeredContexts]);
      };
      Tokenizer.prototype.setEndOffset = function(offset, contextName) {
        var startIndex = this.getContext(contextName).openRange.startIndex;
        var range = new ContextRange(startIndex, offset, contextName);
        var ranges = this.getContext(contextName).ranges;
        range.rangeId = contextName + "." + ranges.length;
        ranges.push(range);
        this.getContext(contextName).openRange = null;
        return range;
      };
      Tokenizer.prototype.runContextCheck = function(contextParams) {
        var this$1 = this;
        var index = contextParams.index;
        this.contextCheckers.forEach(function(contextChecker) {
          var contextName = contextChecker.contextName;
          var openRange = this$1.getContext(contextName).openRange;
          if (!openRange && contextChecker.checkStart(contextParams)) {
            openRange = new ContextRange(index, null, contextName);
            this$1.getContext(contextName).openRange = openRange;
            this$1.dispatch("contextStart", [contextName, index]);
          }
          if (!!openRange && contextChecker.checkEnd(contextParams)) {
            var offset = index - openRange.startIndex + 1;
            var range = this$1.setEndOffset(offset, contextName);
            this$1.dispatch("contextEnd", [contextName, range]);
          }
        });
      };
      Tokenizer.prototype.tokenize = function(text2) {
        this.tokens = [];
        this.resetContextsRanges();
        var chars = Array.from(text2);
        this.dispatch("start");
        for (var i = 0; i < chars.length; i++) {
          var char = chars[i];
          var contextParams = new ContextParams(chars, i);
          this.dispatch("next", [contextParams]);
          this.runContextCheck(contextParams);
          var token = new Token(char);
          this.tokens.push(token);
          this.dispatch("newToken", [token, contextParams]);
        }
        this.dispatch("end", [this.tokens]);
        return this.tokens;
      };
      function isArabicChar(c) {
        return /[\u0600-\u065F\u066A-\u06D2\u06FA-\u06FF]/.test(c);
      }
      function isIsolatedArabicChar(char) {
        return /[\u0630\u0690\u0621\u0631\u0661\u0671\u0622\u0632\u0672\u0692\u06C2\u0623\u0673\u0693\u06C3\u0624\u0694\u06C4\u0625\u0675\u0695\u06C5\u06E5\u0676\u0696\u06C6\u0627\u0677\u0697\u06C7\u0648\u0688\u0698\u06C8\u0689\u0699\u06C9\u068A\u06CA\u066B\u068B\u06CB\u068C\u068D\u06CD\u06FD\u068E\u06EE\u06FE\u062F\u068F\u06CF\u06EF]/.test(char);
      }
      function isTashkeelArabicChar(char) {
        return /[\u0600-\u0605\u060C-\u060E\u0610-\u061B\u061E\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED]/.test(char);
      }
      function isLatinChar(c) {
        return /[A-z]/.test(c);
      }
      function isWhiteSpace(c) {
        return /\s/.test(c);
      }
      function FeatureQuery(font) {
        this.font = font;
        this.features = {};
      }
      function SubstitutionAction(action) {
        this.id = action.id;
        this.tag = action.tag;
        this.substitution = action.substitution;
      }
      function lookupCoverage(glyphIndex, coverage) {
        if (!glyphIndex) {
          return -1;
        }
        switch (coverage.format) {
          case 1:
            return coverage.glyphs.indexOf(glyphIndex);
          case 2:
            var ranges = coverage.ranges;
            for (var i = 0; i < ranges.length; i++) {
              var range = ranges[i];
              if (glyphIndex >= range.start && glyphIndex <= range.end) {
                var offset = glyphIndex - range.start;
                return range.index + offset;
              }
            }
            break;
          default:
            return -1;
        }
        return -1;
      }
      function singleSubstitutionFormat1(glyphIndex, subtable) {
        var substituteIndex = lookupCoverage(glyphIndex, subtable.coverage);
        if (substituteIndex === -1) {
          return null;
        }
        return glyphIndex + subtable.deltaGlyphId;
      }
      function singleSubstitutionFormat2(glyphIndex, subtable) {
        var substituteIndex = lookupCoverage(glyphIndex, subtable.coverage);
        if (substituteIndex === -1) {
          return null;
        }
        return subtable.substitute[substituteIndex];
      }
      function lookupCoverageList(coverageList, contextParams) {
        var lookupList = [];
        for (var i = 0; i < coverageList.length; i++) {
          var coverage = coverageList[i];
          var glyphIndex = contextParams.current;
          glyphIndex = Array.isArray(glyphIndex) ? glyphIndex[0] : glyphIndex;
          var lookupIndex = lookupCoverage(glyphIndex, coverage);
          if (lookupIndex !== -1) {
            lookupList.push(lookupIndex);
          }
        }
        if (lookupList.length !== coverageList.length) {
          return -1;
        }
        return lookupList;
      }
      function chainingSubstitutionFormat3(contextParams, subtable) {
        var lookupsCount = subtable.inputCoverage.length + subtable.lookaheadCoverage.length + subtable.backtrackCoverage.length;
        if (contextParams.context.length < lookupsCount) {
          return [];
        }
        var inputLookups = lookupCoverageList(
          subtable.inputCoverage,
          contextParams
        );
        if (inputLookups === -1) {
          return [];
        }
        var lookaheadOffset = subtable.inputCoverage.length - 1;
        if (contextParams.lookahead.length < subtable.lookaheadCoverage.length) {
          return [];
        }
        var lookaheadContext = contextParams.lookahead.slice(lookaheadOffset);
        while (lookaheadContext.length && isTashkeelArabicChar(lookaheadContext[0].char)) {
          lookaheadContext.shift();
        }
        var lookaheadParams = new ContextParams(lookaheadContext, 0);
        var lookaheadLookups = lookupCoverageList(
          subtable.lookaheadCoverage,
          lookaheadParams
        );
        var backtrackContext = [].concat(contextParams.backtrack);
        backtrackContext.reverse();
        while (backtrackContext.length && isTashkeelArabicChar(backtrackContext[0].char)) {
          backtrackContext.shift();
        }
        if (backtrackContext.length < subtable.backtrackCoverage.length) {
          return [];
        }
        var backtrackParams = new ContextParams(backtrackContext, 0);
        var backtrackLookups = lookupCoverageList(
          subtable.backtrackCoverage,
          backtrackParams
        );
        var contextRulesMatch = inputLookups.length === subtable.inputCoverage.length && lookaheadLookups.length === subtable.lookaheadCoverage.length && backtrackLookups.length === subtable.backtrackCoverage.length;
        var substitutions = [];
        if (contextRulesMatch) {
          for (var i = 0; i < subtable.lookupRecords.length; i++) {
            var lookupRecord = subtable.lookupRecords[i];
            var lookupListIndex = lookupRecord.lookupListIndex;
            var lookupTable = this.getLookupByIndex(lookupListIndex);
            for (var s = 0; s < lookupTable.subtables.length; s++) {
              var subtable$1 = lookupTable.subtables[s];
              var lookup = this.getLookupMethod(lookupTable, subtable$1);
              var substitutionType = this.getSubstitutionType(lookupTable, subtable$1);
              if (substitutionType === "12") {
                for (var n = 0; n < inputLookups.length; n++) {
                  var glyphIndex = contextParams.get(n);
                  var substitution = lookup(glyphIndex);
                  if (substitution) {
                    substitutions.push(substitution);
                  }
                }
              }
            }
          }
        }
        return substitutions;
      }
      function ligatureSubstitutionFormat1(contextParams, subtable) {
        var glyphIndex = contextParams.current;
        var ligSetIndex = lookupCoverage(glyphIndex, subtable.coverage);
        if (ligSetIndex === -1) {
          return null;
        }
        var ligature;
        var ligatureSet = subtable.ligatureSets[ligSetIndex];
        for (var s = 0; s < ligatureSet.length; s++) {
          ligature = ligatureSet[s];
          for (var l = 0; l < ligature.components.length; l++) {
            var lookaheadItem = contextParams.lookahead[l];
            var component = ligature.components[l];
            if (lookaheadItem !== component) {
              break;
            }
            if (l === ligature.components.length - 1) {
              return ligature;
            }
          }
        }
        return null;
      }
      function decompositionSubstitutionFormat1(glyphIndex, subtable) {
        var substituteIndex = lookupCoverage(glyphIndex, subtable.coverage);
        if (substituteIndex === -1) {
          return null;
        }
        return subtable.sequences[substituteIndex];
      }
      FeatureQuery.prototype.getDefaultScriptFeaturesIndexes = function() {
        var scripts = this.font.tables.gsub.scripts;
        for (var s = 0; s < scripts.length; s++) {
          var script = scripts[s];
          if (script.tag === "DFLT") {
            return script.script.defaultLangSys.featureIndexes;
          }
        }
        return [];
      };
      FeatureQuery.prototype.getScriptFeaturesIndexes = function(scriptTag) {
        var tables2 = this.font.tables;
        if (!tables2.gsub) {
          return [];
        }
        if (!scriptTag) {
          return this.getDefaultScriptFeaturesIndexes();
        }
        var scripts = this.font.tables.gsub.scripts;
        for (var i = 0; i < scripts.length; i++) {
          var script = scripts[i];
          if (script.tag === scriptTag && script.script.defaultLangSys) {
            return script.script.defaultLangSys.featureIndexes;
          } else {
            var langSysRecords = script.langSysRecords;
            if (!!langSysRecords) {
              for (var j = 0; j < langSysRecords.length; j++) {
                var langSysRecord = langSysRecords[j];
                if (langSysRecord.tag === scriptTag) {
                  var langSys = langSysRecord.langSys;
                  return langSys.featureIndexes;
                }
              }
            }
          }
        }
        return this.getDefaultScriptFeaturesIndexes();
      };
      FeatureQuery.prototype.mapTagsToFeatures = function(features, scriptTag) {
        var tags = {};
        for (var i = 0; i < features.length; i++) {
          var tag = features[i].tag;
          var feature = features[i].feature;
          tags[tag] = feature;
        }
        this.features[scriptTag].tags = tags;
      };
      FeatureQuery.prototype.getScriptFeatures = function(scriptTag) {
        var features = this.features[scriptTag];
        if (this.features.hasOwnProperty(scriptTag)) {
          return features;
        }
        var featuresIndexes = this.getScriptFeaturesIndexes(scriptTag);
        if (!featuresIndexes) {
          return null;
        }
        var gsub2 = this.font.tables.gsub;
        features = featuresIndexes.map(function(index) {
          return gsub2.features[index];
        });
        this.features[scriptTag] = features;
        this.mapTagsToFeatures(features, scriptTag);
        return features;
      };
      FeatureQuery.prototype.getSubstitutionType = function(lookupTable, subtable) {
        var lookupType = lookupTable.lookupType.toString();
        var substFormat = subtable.substFormat.toString();
        return lookupType + substFormat;
      };
      FeatureQuery.prototype.getLookupMethod = function(lookupTable, subtable) {
        var this$1 = this;
        var substitutionType = this.getSubstitutionType(lookupTable, subtable);
        switch (substitutionType) {
          case "11":
            return function(glyphIndex) {
              return singleSubstitutionFormat1.apply(
                this$1,
                [glyphIndex, subtable]
              );
            };
          case "12":
            return function(glyphIndex) {
              return singleSubstitutionFormat2.apply(
                this$1,
                [glyphIndex, subtable]
              );
            };
          case "63":
            return function(contextParams) {
              return chainingSubstitutionFormat3.apply(
                this$1,
                [contextParams, subtable]
              );
            };
          case "41":
            return function(contextParams) {
              return ligatureSubstitutionFormat1.apply(
                this$1,
                [contextParams, subtable]
              );
            };
          case "21":
            return function(glyphIndex) {
              return decompositionSubstitutionFormat1.apply(
                this$1,
                [glyphIndex, subtable]
              );
            };
          default:
            throw new Error(
              "lookupType: " + lookupTable.lookupType + " - substFormat: " + subtable.substFormat + " is not yet supported"
            );
        }
      };
      FeatureQuery.prototype.lookupFeature = function(query) {
        var contextParams = query.contextParams;
        var currentIndex = contextParams.index;
        var feature = this.getFeature({
          tag: query.tag,
          script: query.script
        });
        if (!feature) {
          return new Error(
            "font '" + this.font.names.fullName.en + "' doesn't support feature '" + query.tag + "' for script '" + query.script + "'."
          );
        }
        var lookups = this.getFeatureLookups(feature);
        var substitutions = [].concat(contextParams.context);
        for (var l = 0; l < lookups.length; l++) {
          var lookupTable = lookups[l];
          var subtables = this.getLookupSubtables(lookupTable);
          for (var s = 0; s < subtables.length; s++) {
            var subtable = subtables[s];
            var substType = this.getSubstitutionType(lookupTable, subtable);
            var lookup = this.getLookupMethod(lookupTable, subtable);
            var substitution = void 0;
            switch (substType) {
              case "11":
                substitution = lookup(contextParams.current);
                if (substitution) {
                  substitutions.splice(currentIndex, 1, new SubstitutionAction({
                    id: 11,
                    tag: query.tag,
                    substitution
                  }));
                }
                break;
              case "12":
                substitution = lookup(contextParams.current);
                if (substitution) {
                  substitutions.splice(currentIndex, 1, new SubstitutionAction({
                    id: 12,
                    tag: query.tag,
                    substitution
                  }));
                }
                break;
              case "63":
                substitution = lookup(contextParams);
                if (Array.isArray(substitution) && substitution.length) {
                  substitutions.splice(currentIndex, 1, new SubstitutionAction({
                    id: 63,
                    tag: query.tag,
                    substitution
                  }));
                }
                break;
              case "41":
                substitution = lookup(contextParams);
                if (substitution) {
                  substitutions.splice(currentIndex, 1, new SubstitutionAction({
                    id: 41,
                    tag: query.tag,
                    substitution
                  }));
                }
                break;
              case "21":
                substitution = lookup(contextParams.current);
                if (substitution) {
                  substitutions.splice(currentIndex, 1, new SubstitutionAction({
                    id: 21,
                    tag: query.tag,
                    substitution
                  }));
                }
                break;
            }
            contextParams = new ContextParams(substitutions, currentIndex);
            if (Array.isArray(substitution) && !substitution.length) {
              continue;
            }
            substitution = null;
          }
        }
        return substitutions.length ? substitutions : null;
      };
      FeatureQuery.prototype.supports = function(query) {
        if (!query.script) {
          return false;
        }
        this.getScriptFeatures(query.script);
        var supportedScript = this.features.hasOwnProperty(query.script);
        if (!query.tag) {
          return supportedScript;
        }
        var supportedFeature = this.features[query.script].some(function(feature) {
          return feature.tag === query.tag;
        });
        return supportedScript && supportedFeature;
      };
      FeatureQuery.prototype.getLookupSubtables = function(lookupTable) {
        return lookupTable.subtables || null;
      };
      FeatureQuery.prototype.getLookupByIndex = function(index) {
        var lookups = this.font.tables.gsub.lookups;
        return lookups[index] || null;
      };
      FeatureQuery.prototype.getFeatureLookups = function(feature) {
        return feature.lookupListIndexes.map(this.getLookupByIndex.bind(this));
      };
      FeatureQuery.prototype.getFeature = function getFeature(query) {
        if (!this.font) {
          return { FAIL: "No font was found" };
        }
        if (!this.features.hasOwnProperty(query.script)) {
          this.getScriptFeatures(query.script);
        }
        var scriptFeatures = this.features[query.script];
        if (!scriptFeatures) {
          return { FAIL: "No feature for script " + query.script };
        }
        if (!scriptFeatures.tags[query.tag]) {
          return null;
        }
        return this.features[query.script].tags[query.tag];
      };
      function arabicWordStartCheck(contextParams) {
        var char = contextParams.current;
        var prevChar = contextParams.get(-1);
        return (
          // ? arabic first char
          prevChar === null && isArabicChar(char) || // ? arabic char preceded with a non arabic char
          !isArabicChar(prevChar) && isArabicChar(char)
        );
      }
      function arabicWordEndCheck(contextParams) {
        var nextChar = contextParams.get(1);
        return (
          // ? last arabic char
          nextChar === null || // ? next char is not arabic
          !isArabicChar(nextChar)
        );
      }
      var arabicWordCheck = {
        startCheck: arabicWordStartCheck,
        endCheck: arabicWordEndCheck
      };
      function arabicSentenceStartCheck(contextParams) {
        var char = contextParams.current;
        var prevChar = contextParams.get(-1);
        return (
          // ? an arabic char preceded with a non arabic char
          (isArabicChar(char) || isTashkeelArabicChar(char)) && !isArabicChar(prevChar)
        );
      }
      function arabicSentenceEndCheck(contextParams) {
        var nextChar = contextParams.get(1);
        switch (true) {
          case nextChar === null:
            return true;
          case (!isArabicChar(nextChar) && !isTashkeelArabicChar(nextChar)):
            var nextIsWhitespace = isWhiteSpace(nextChar);
            if (!nextIsWhitespace) {
              return true;
            }
            if (nextIsWhitespace) {
              var arabicCharAhead = false;
              arabicCharAhead = contextParams.lookahead.some(
                function(c) {
                  return isArabicChar(c) || isTashkeelArabicChar(c);
                }
              );
              if (!arabicCharAhead) {
                return true;
              }
            }
            break;
          default:
            return false;
        }
      }
      var arabicSentenceCheck = {
        startCheck: arabicSentenceStartCheck,
        endCheck: arabicSentenceEndCheck
      };
      function singleSubstitutionFormat1$1(action, tokens, index) {
        tokens[index].setState(action.tag, action.substitution);
      }
      function singleSubstitutionFormat2$1(action, tokens, index) {
        tokens[index].setState(action.tag, action.substitution);
      }
      function chainingSubstitutionFormat3$1(action, tokens, index) {
        action.substitution.forEach(function(subst, offset) {
          var token = tokens[index + offset];
          token.setState(action.tag, subst);
        });
      }
      function ligatureSubstitutionFormat1$1(action, tokens, index) {
        var token = tokens[index];
        token.setState(action.tag, action.substitution.ligGlyph);
        var compsCount = action.substitution.components.length;
        for (var i = 0; i < compsCount; i++) {
          token = tokens[index + i + 1];
          token.setState("deleted", true);
        }
      }
      var SUBSTITUTIONS = {
        11: singleSubstitutionFormat1$1,
        12: singleSubstitutionFormat2$1,
        63: chainingSubstitutionFormat3$1,
        41: ligatureSubstitutionFormat1$1
      };
      function applySubstitution(action, tokens, index) {
        if (action instanceof SubstitutionAction && SUBSTITUTIONS[action.id]) {
          SUBSTITUTIONS[action.id](action, tokens, index);
        }
      }
      function willConnectPrev(charContextParams) {
        var backtrack = [].concat(charContextParams.backtrack);
        for (var i = backtrack.length - 1; i >= 0; i--) {
          var prevChar = backtrack[i];
          var isolated = isIsolatedArabicChar(prevChar);
          var tashkeel = isTashkeelArabicChar(prevChar);
          if (!isolated && !tashkeel) {
            return true;
          }
          if (isolated) {
            return false;
          }
        }
        return false;
      }
      function willConnectNext(charContextParams) {
        if (isIsolatedArabicChar(charContextParams.current)) {
          return false;
        }
        for (var i = 0; i < charContextParams.lookahead.length; i++) {
          var nextChar = charContextParams.lookahead[i];
          var tashkeel = isTashkeelArabicChar(nextChar);
          if (!tashkeel) {
            return true;
          }
        }
        return false;
      }
      function arabicPresentationForms(range) {
        var this$1 = this;
        var script = "arab";
        var tags = this.featuresTags[script];
        var tokens = this.tokenizer.getRangeTokens(range);
        if (tokens.length === 1) {
          return;
        }
        var contextParams = new ContextParams(
          tokens.map(
            function(token) {
              return token.getState("glyphIndex");
            }
          ),
          0
        );
        var charContextParams = new ContextParams(
          tokens.map(
            function(token) {
              return token.char;
            }
          ),
          0
        );
        tokens.forEach(function(token, index) {
          if (isTashkeelArabicChar(token.char)) {
            return;
          }
          contextParams.setCurrentIndex(index);
          charContextParams.setCurrentIndex(index);
          var CONNECT = 0;
          if (willConnectPrev(charContextParams)) {
            CONNECT |= 1;
          }
          if (willConnectNext(charContextParams)) {
            CONNECT |= 2;
          }
          var tag;
          switch (CONNECT) {
            case 1:
              tag = "fina";
              break;
            case 2:
              tag = "init";
              break;
            case 3:
              tag = "medi";
              break;
          }
          if (tags.indexOf(tag) === -1) {
            return;
          }
          var substitutions = this$1.query.lookupFeature({
            tag,
            script,
            contextParams
          });
          if (substitutions instanceof Error) {
            return console.info(substitutions.message);
          }
          substitutions.forEach(function(action, index2) {
            if (action instanceof SubstitutionAction) {
              applySubstitution(action, tokens, index2);
              contextParams.context[index2] = action.substitution;
            }
          });
        });
      }
      function getContextParams(tokens, index) {
        var context = tokens.map(function(token) {
          return token.activeState.value;
        });
        return new ContextParams(context, index || 0);
      }
      function arabicRequiredLigatures(range) {
        var this$1 = this;
        var script = "arab";
        var tokens = this.tokenizer.getRangeTokens(range);
        var contextParams = getContextParams(tokens);
        contextParams.context.forEach(function(glyphIndex, index) {
          contextParams.setCurrentIndex(index);
          var substitutions = this$1.query.lookupFeature({
            tag: "rlig",
            script,
            contextParams
          });
          if (substitutions.length) {
            substitutions.forEach(
              function(action) {
                return applySubstitution(action, tokens, index);
              }
            );
            contextParams = getContextParams(tokens);
          }
        });
      }
      function latinWordStartCheck(contextParams) {
        var char = contextParams.current;
        var prevChar = contextParams.get(-1);
        return (
          // ? latin first char
          prevChar === null && isLatinChar(char) || // ? latin char preceded with a non latin char
          !isLatinChar(prevChar) && isLatinChar(char)
        );
      }
      function latinWordEndCheck(contextParams) {
        var nextChar = contextParams.get(1);
        return (
          // ? last latin char
          nextChar === null || // ? next char is not latin
          !isLatinChar(nextChar)
        );
      }
      var latinWordCheck = {
        startCheck: latinWordStartCheck,
        endCheck: latinWordEndCheck
      };
      function getContextParams$1(tokens, index) {
        var context = tokens.map(function(token) {
          return token.activeState.value;
        });
        return new ContextParams(context, index || 0);
      }
      function latinLigature(range) {
        var this$1 = this;
        var script = "latn";
        var tokens = this.tokenizer.getRangeTokens(range);
        var contextParams = getContextParams$1(tokens);
        contextParams.context.forEach(function(glyphIndex, index) {
          contextParams.setCurrentIndex(index);
          var substitutions = this$1.query.lookupFeature({
            tag: "liga",
            script,
            contextParams
          });
          if (substitutions.length) {
            substitutions.forEach(
              function(action) {
                return applySubstitution(action, tokens, index);
              }
            );
            contextParams = getContextParams$1(tokens);
          }
        });
      }
      function Bidi(baseDir) {
        this.baseDir = baseDir || "ltr";
        this.tokenizer = new Tokenizer();
        this.featuresTags = {};
      }
      Bidi.prototype.setText = function(text2) {
        this.text = text2;
      };
      Bidi.prototype.contextChecks = {
        latinWordCheck,
        arabicWordCheck,
        arabicSentenceCheck
      };
      function registerContextChecker(checkId) {
        var check2 = this.contextChecks[checkId + "Check"];
        return this.tokenizer.registerContextChecker(
          checkId,
          check2.startCheck,
          check2.endCheck
        );
      }
      function tokenizeText() {
        registerContextChecker.call(this, "latinWord");
        registerContextChecker.call(this, "arabicWord");
        registerContextChecker.call(this, "arabicSentence");
        return this.tokenizer.tokenize(this.text);
      }
      function reverseArabicSentences() {
        var this$1 = this;
        var ranges = this.tokenizer.getContextRanges("arabicSentence");
        ranges.forEach(function(range) {
          var rangeTokens = this$1.tokenizer.getRangeTokens(range);
          this$1.tokenizer.replaceRange(
            range.startIndex,
            range.endOffset,
            rangeTokens.reverse()
          );
        });
      }
      Bidi.prototype.registerFeatures = function(script, tags) {
        var this$1 = this;
        var supportedTags = tags.filter(
          function(tag) {
            return this$1.query.supports({ script, tag });
          }
        );
        if (!this.featuresTags.hasOwnProperty(script)) {
          this.featuresTags[script] = supportedTags;
        } else {
          this.featuresTags[script] = this.featuresTags[script].concat(supportedTags);
        }
      };
      Bidi.prototype.applyFeatures = function(font, features) {
        if (!font) {
          throw new Error(
            "No valid font was provided to apply features"
          );
        }
        if (!this.query) {
          this.query = new FeatureQuery(font);
        }
        for (var f = 0; f < features.length; f++) {
          var feature = features[f];
          if (!this.query.supports({ script: feature.script })) {
            continue;
          }
          this.registerFeatures(feature.script, feature.tags);
        }
      };
      Bidi.prototype.registerModifier = function(modifierId, condition, modifier) {
        this.tokenizer.registerModifier(modifierId, condition, modifier);
      };
      function checkGlyphIndexStatus() {
        if (this.tokenizer.registeredModifiers.indexOf("glyphIndex") === -1) {
          throw new Error(
            "glyphIndex modifier is required to apply arabic presentation features."
          );
        }
      }
      function applyArabicPresentationForms() {
        var this$1 = this;
        var script = "arab";
        if (!this.featuresTags.hasOwnProperty(script)) {
          return;
        }
        checkGlyphIndexStatus.call(this);
        var ranges = this.tokenizer.getContextRanges("arabicWord");
        ranges.forEach(function(range) {
          arabicPresentationForms.call(this$1, range);
        });
      }
      function applyArabicRequireLigatures() {
        var this$1 = this;
        var script = "arab";
        if (!this.featuresTags.hasOwnProperty(script)) {
          return;
        }
        var tags = this.featuresTags[script];
        if (tags.indexOf("rlig") === -1) {
          return;
        }
        checkGlyphIndexStatus.call(this);
        var ranges = this.tokenizer.getContextRanges("arabicWord");
        ranges.forEach(function(range) {
          arabicRequiredLigatures.call(this$1, range);
        });
      }
      function applyLatinLigatures() {
        var this$1 = this;
        var script = "latn";
        if (!this.featuresTags.hasOwnProperty(script)) {
          return;
        }
        var tags = this.featuresTags[script];
        if (tags.indexOf("liga") === -1) {
          return;
        }
        checkGlyphIndexStatus.call(this);
        var ranges = this.tokenizer.getContextRanges("latinWord");
        ranges.forEach(function(range) {
          latinLigature.call(this$1, range);
        });
      }
      Bidi.prototype.checkContextReady = function(contextId) {
        return !!this.tokenizer.getContext(contextId);
      };
      Bidi.prototype.applyFeaturesToContexts = function() {
        if (this.checkContextReady("arabicWord")) {
          applyArabicPresentationForms.call(this);
          applyArabicRequireLigatures.call(this);
        }
        if (this.checkContextReady("latinWord")) {
          applyLatinLigatures.call(this);
        }
        if (this.checkContextReady("arabicSentence")) {
          reverseArabicSentences.call(this);
        }
      };
      Bidi.prototype.processText = function(text2) {
        if (!this.text || this.text !== text2) {
          this.setText(text2);
          tokenizeText.call(this);
          this.applyFeaturesToContexts();
        }
      };
      Bidi.prototype.getBidiText = function(text2) {
        this.processText(text2);
        return this.tokenizer.getText();
      };
      Bidi.prototype.getTextGlyphs = function(text2) {
        this.processText(text2);
        var indexes = [];
        for (var i = 0; i < this.tokenizer.tokens.length; i++) {
          var token = this.tokenizer.tokens[i];
          if (token.state.deleted) {
            continue;
          }
          var index = token.activeState.value;
          indexes.push(Array.isArray(index) ? index[0] : index);
        }
        return indexes;
      };
      function Font(options) {
        options = options || {};
        options.tables = options.tables || {};
        if (!options.empty) {
          checkArgument(options.familyName, "When creating a new Font object, familyName is required.");
          checkArgument(options.styleName, "When creating a new Font object, styleName is required.");
          checkArgument(options.unitsPerEm, "When creating a new Font object, unitsPerEm is required.");
          checkArgument(options.ascender, "When creating a new Font object, ascender is required.");
          checkArgument(options.descender <= 0, "When creating a new Font object, negative descender value is required.");
          this.names = {
            fontFamily: { en: options.familyName || " " },
            fontSubfamily: { en: options.styleName || " " },
            fullName: { en: options.fullName || options.familyName + " " + options.styleName },
            // postScriptName may not contain any whitespace
            postScriptName: { en: options.postScriptName || (options.familyName + options.styleName).replace(/\s/g, "") },
            designer: { en: options.designer || " " },
            designerURL: { en: options.designerURL || " " },
            manufacturer: { en: options.manufacturer || " " },
            manufacturerURL: { en: options.manufacturerURL || " " },
            license: { en: options.license || " " },
            licenseURL: { en: options.licenseURL || " " },
            version: { en: options.version || "Version 0.1" },
            description: { en: options.description || " " },
            copyright: { en: options.copyright || " " },
            trademark: { en: options.trademark || " " }
          };
          this.unitsPerEm = options.unitsPerEm || 1e3;
          this.ascender = options.ascender;
          this.descender = options.descender;
          this.createdTimestamp = options.createdTimestamp;
          this.tables = Object.assign(options.tables, {
            os2: Object.assign({
              usWeightClass: options.weightClass || this.usWeightClasses.MEDIUM,
              usWidthClass: options.widthClass || this.usWidthClasses.MEDIUM,
              fsSelection: options.fsSelection || this.fsSelectionValues.REGULAR
            }, options.tables.os2)
          });
        }
        this.supported = true;
        this.glyphs = new glyphset.GlyphSet(this, options.glyphs || []);
        this.encoding = new DefaultEncoding(this);
        this.position = new Position(this);
        this.substitution = new Substitution(this);
        this.tables = this.tables || {};
        this._push = null;
        this._hmtxTableData = {};
        Object.defineProperty(this, "hinting", {
          get: function() {
            if (this._hinting) {
              return this._hinting;
            }
            if (this.outlinesFormat === "truetype") {
              return this._hinting = new Hinting(this);
            }
          }
        });
      }
      Font.prototype.hasChar = function(c) {
        return this.encoding.charToGlyphIndex(c) !== null;
      };
      Font.prototype.charToGlyphIndex = function(s) {
        return this.encoding.charToGlyphIndex(s);
      };
      Font.prototype.charToGlyph = function(c) {
        var glyphIndex = this.charToGlyphIndex(c);
        var glyph = this.glyphs.get(glyphIndex);
        if (!glyph) {
          glyph = this.glyphs.get(0);
        }
        return glyph;
      };
      Font.prototype.updateFeatures = function(options) {
        return this.defaultRenderOptions.features.map(function(feature) {
          if (feature.script === "latn") {
            return {
              script: "latn",
              tags: feature.tags.filter(function(tag) {
                return options[tag];
              })
            };
          } else {
            return feature;
          }
        });
      };
      Font.prototype.stringToGlyphs = function(s, options) {
        var this$1 = this;
        var bidi = new Bidi();
        var charToGlyphIndexMod = function(token) {
          return this$1.charToGlyphIndex(token.char);
        };
        bidi.registerModifier("glyphIndex", null, charToGlyphIndexMod);
        var features = options ? this.updateFeatures(options.features) : this.defaultRenderOptions.features;
        bidi.applyFeatures(this, features);
        var indexes = bidi.getTextGlyphs(s);
        var length = indexes.length;
        var glyphs = new Array(length);
        var notdef = this.glyphs.get(0);
        for (var i = 0; i < length; i += 1) {
          glyphs[i] = this.glyphs.get(indexes[i]) || notdef;
        }
        return glyphs;
      };
      Font.prototype.nameToGlyphIndex = function(name) {
        return this.glyphNames.nameToGlyphIndex(name);
      };
      Font.prototype.nameToGlyph = function(name) {
        var glyphIndex = this.nameToGlyphIndex(name);
        var glyph = this.glyphs.get(glyphIndex);
        if (!glyph) {
          glyph = this.glyphs.get(0);
        }
        return glyph;
      };
      Font.prototype.glyphIndexToName = function(gid) {
        if (!this.glyphNames.glyphIndexToName) {
          return "";
        }
        return this.glyphNames.glyphIndexToName(gid);
      };
      Font.prototype.getKerningValue = function(leftGlyph, rightGlyph) {
        leftGlyph = leftGlyph.index || leftGlyph;
        rightGlyph = rightGlyph.index || rightGlyph;
        var gposKerning = this.position.defaultKerningTables;
        if (gposKerning) {
          return this.position.getKerningValue(gposKerning, leftGlyph, rightGlyph);
        }
        return this.kerningPairs[leftGlyph + "," + rightGlyph] || 0;
      };
      Font.prototype.defaultRenderOptions = {
        kerning: true,
        features: [
          /**
           * these 4 features are required to render Arabic text properly
           * and shouldn't be turned off when rendering arabic text.
           */
          { script: "arab", tags: ["init", "medi", "fina", "rlig"] },
          { script: "latn", tags: ["liga", "rlig"] }
        ]
      };
      Font.prototype.forEachGlyph = function(text2, x, y, fontSize, options, callback) {
        x = x !== void 0 ? x : 0;
        y = y !== void 0 ? y : 0;
        fontSize = fontSize !== void 0 ? fontSize : 72;
        options = Object.assign({}, this.defaultRenderOptions, options);
        var fontScale = 1 / this.unitsPerEm * fontSize;
        var glyphs = this.stringToGlyphs(text2, options);
        var kerningLookups;
        if (options.kerning) {
          var script = options.script || this.position.getDefaultScriptName();
          kerningLookups = this.position.getKerningTables(script, options.language);
        }
        for (var i = 0; i < glyphs.length; i += 1) {
          var glyph = glyphs[i];
          callback.call(this, glyph, x, y, fontSize, options);
          if (glyph.advanceWidth) {
            x += glyph.advanceWidth * fontScale;
          }
          if (options.kerning && i < glyphs.length - 1) {
            var kerningValue = kerningLookups ? this.position.getKerningValue(kerningLookups, glyph.index, glyphs[i + 1].index) : this.getKerningValue(glyph, glyphs[i + 1]);
            x += kerningValue * fontScale;
          }
          if (options.letterSpacing) {
            x += options.letterSpacing * fontSize;
          } else if (options.tracking) {
            x += options.tracking / 1e3 * fontSize;
          }
        }
        return x;
      };
      Font.prototype.getPath = function(text2, x, y, fontSize, options) {
        var fullPath = new Path();
        this.forEachGlyph(text2, x, y, fontSize, options, function(glyph, gX, gY, gFontSize) {
          var glyphPath = glyph.getPath(gX, gY, gFontSize, options, this);
          fullPath.extend(glyphPath);
        });
        return fullPath;
      };
      Font.prototype.getPaths = function(text2, x, y, fontSize, options) {
        var glyphPaths = [];
        this.forEachGlyph(text2, x, y, fontSize, options, function(glyph, gX, gY, gFontSize) {
          var glyphPath = glyph.getPath(gX, gY, gFontSize, options, this);
          glyphPaths.push(glyphPath);
        });
        return glyphPaths;
      };
      Font.prototype.getAdvanceWidth = function(text2, fontSize, options) {
        return this.forEachGlyph(text2, 0, 0, fontSize, options, function() {
        });
      };
      Font.prototype.draw = function(ctx, text2, x, y, fontSize, options) {
        this.getPath(text2, x, y, fontSize, options).draw(ctx);
      };
      Font.prototype.drawPoints = function(ctx, text2, x, y, fontSize, options) {
        this.forEachGlyph(text2, x, y, fontSize, options, function(glyph, gX, gY, gFontSize) {
          glyph.drawPoints(ctx, gX, gY, gFontSize);
        });
      };
      Font.prototype.drawMetrics = function(ctx, text2, x, y, fontSize, options) {
        this.forEachGlyph(text2, x, y, fontSize, options, function(glyph, gX, gY, gFontSize) {
          glyph.drawMetrics(ctx, gX, gY, gFontSize);
        });
      };
      Font.prototype.getEnglishName = function(name) {
        var translations = this.names[name];
        if (translations) {
          return translations.en;
        }
      };
      Font.prototype.validate = function() {
        var _this = this;
        function assert(predicate, message) {
        }
        function assertNamePresent(name) {
          var englishName = _this.getEnglishName(name);
          assert(englishName && englishName.trim().length > 0);
        }
        assertNamePresent("fontFamily");
        assertNamePresent("weightName");
        assertNamePresent("manufacturer");
        assertNamePresent("copyright");
        assertNamePresent("version");
        assert(this.unitsPerEm > 0);
      };
      Font.prototype.toTables = function() {
        return sfnt.fontToTable(this);
      };
      Font.prototype.toBuffer = function() {
        console.warn("Font.toBuffer is deprecated. Use Font.toArrayBuffer instead.");
        return this.toArrayBuffer();
      };
      Font.prototype.toArrayBuffer = function() {
        var sfntTable = this.toTables();
        var bytes = sfntTable.encode();
        var buffer2 = new ArrayBuffer(bytes.length);
        var intArray = new Uint8Array(buffer2);
        for (var i = 0; i < bytes.length; i++) {
          intArray[i] = bytes[i];
        }
        return buffer2;
      };
      Font.prototype.download = function(fileName) {
        var familyName = this.getEnglishName("fontFamily");
        var styleName = this.getEnglishName("fontSubfamily");
        fileName = fileName || familyName.replace(/\s/g, "") + "-" + styleName + ".otf";
        var arrayBuffer = this.toArrayBuffer();
        if (isBrowser()) {
          window.URL = window.URL || window.webkitURL;
          if (window.URL) {
            var dataView = new DataView(arrayBuffer);
            var blob = new Blob([dataView], { type: "font/opentype" });
            var link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = fileName;
            var event = document.createEvent("MouseEvents");
            event.initEvent("click", true, false);
            link.dispatchEvent(event);
          } else {
            console.warn("Font file could not be downloaded. Try using a different browser.");
          }
        } else {
          var fs2 = __require("fs");
          var buffer2 = arrayBufferToNodeBuffer(arrayBuffer);
          fs2.writeFileSync(fileName, buffer2);
        }
      };
      Font.prototype.fsSelectionValues = {
        ITALIC: 1,
        //1
        UNDERSCORE: 2,
        //2
        NEGATIVE: 4,
        //4
        OUTLINED: 8,
        //8
        STRIKEOUT: 16,
        //16
        BOLD: 32,
        //32
        REGULAR: 64,
        //64
        USER_TYPO_METRICS: 128,
        //128
        WWS: 256,
        //256
        OBLIQUE: 512
        //512
      };
      Font.prototype.usWidthClasses = {
        ULTRA_CONDENSED: 1,
        EXTRA_CONDENSED: 2,
        CONDENSED: 3,
        SEMI_CONDENSED: 4,
        MEDIUM: 5,
        SEMI_EXPANDED: 6,
        EXPANDED: 7,
        EXTRA_EXPANDED: 8,
        ULTRA_EXPANDED: 9
      };
      Font.prototype.usWeightClasses = {
        THIN: 100,
        EXTRA_LIGHT: 200,
        LIGHT: 300,
        NORMAL: 400,
        MEDIUM: 500,
        SEMI_BOLD: 600,
        BOLD: 700,
        EXTRA_BOLD: 800,
        BLACK: 900
      };
      function addName(name, names) {
        var nameString = JSON.stringify(name);
        var nameID = 256;
        for (var nameKey in names) {
          var n = parseInt(nameKey);
          if (!n || n < 256) {
            continue;
          }
          if (JSON.stringify(names[nameKey]) === nameString) {
            return n;
          }
          if (nameID <= n) {
            nameID = n + 1;
          }
        }
        names[nameID] = name;
        return nameID;
      }
      function makeFvarAxis(n, axis, names) {
        var nameID = addName(axis.name, names);
        return [
          { name: "tag_" + n, type: "TAG", value: axis.tag },
          { name: "minValue_" + n, type: "FIXED", value: axis.minValue << 16 },
          { name: "defaultValue_" + n, type: "FIXED", value: axis.defaultValue << 16 },
          { name: "maxValue_" + n, type: "FIXED", value: axis.maxValue << 16 },
          { name: "flags_" + n, type: "USHORT", value: 0 },
          { name: "nameID_" + n, type: "USHORT", value: nameID }
        ];
      }
      function parseFvarAxis(data, start, names) {
        var axis = {};
        var p = new parse2.Parser(data, start);
        axis.tag = p.parseTag();
        axis.minValue = p.parseFixed();
        axis.defaultValue = p.parseFixed();
        axis.maxValue = p.parseFixed();
        p.skip("uShort", 1);
        axis.name = names[p.parseUShort()] || {};
        return axis;
      }
      function makeFvarInstance(n, inst, axes, names) {
        var nameID = addName(inst.name, names);
        var fields = [
          { name: "nameID_" + n, type: "USHORT", value: nameID },
          { name: "flags_" + n, type: "USHORT", value: 0 }
        ];
        for (var i = 0; i < axes.length; ++i) {
          var axisTag = axes[i].tag;
          fields.push({
            name: "axis_" + n + " " + axisTag,
            type: "FIXED",
            value: inst.coordinates[axisTag] << 16
          });
        }
        return fields;
      }
      function parseFvarInstance(data, start, axes, names) {
        var inst = {};
        var p = new parse2.Parser(data, start);
        inst.name = names[p.parseUShort()] || {};
        p.skip("uShort", 1);
        inst.coordinates = {};
        for (var i = 0; i < axes.length; ++i) {
          inst.coordinates[axes[i].tag] = p.parseFixed();
        }
        return inst;
      }
      function makeFvarTable(fvar2, names) {
        var result = new table2.Table("fvar", [
          { name: "version", type: "ULONG", value: 65536 },
          { name: "offsetToData", type: "USHORT", value: 0 },
          { name: "countSizePairs", type: "USHORT", value: 2 },
          { name: "axisCount", type: "USHORT", value: fvar2.axes.length },
          { name: "axisSize", type: "USHORT", value: 20 },
          { name: "instanceCount", type: "USHORT", value: fvar2.instances.length },
          { name: "instanceSize", type: "USHORT", value: 4 + fvar2.axes.length * 4 }
        ]);
        result.offsetToData = result.sizeOf();
        for (var i = 0; i < fvar2.axes.length; i++) {
          result.fields = result.fields.concat(makeFvarAxis(i, fvar2.axes[i], names));
        }
        for (var j = 0; j < fvar2.instances.length; j++) {
          result.fields = result.fields.concat(makeFvarInstance(j, fvar2.instances[j], fvar2.axes, names));
        }
        return result;
      }
      function parseFvarTable(data, start, names) {
        var p = new parse2.Parser(data, start);
        var tableVersion = p.parseULong();
        check.argument(tableVersion === 65536, "Unsupported fvar table version.");
        var offsetToData = p.parseOffset16();
        p.skip("uShort", 1);
        var axisCount = p.parseUShort();
        var axisSize = p.parseUShort();
        var instanceCount = p.parseUShort();
        var instanceSize = p.parseUShort();
        var axes = [];
        for (var i = 0; i < axisCount; i++) {
          axes.push(parseFvarAxis(data, start + offsetToData + i * axisSize, names));
        }
        var instances = [];
        var instanceStart = start + offsetToData + axisCount * axisSize;
        for (var j = 0; j < instanceCount; j++) {
          instances.push(parseFvarInstance(data, instanceStart + j * instanceSize, axes, names));
        }
        return { axes, instances };
      }
      var fvar = { make: makeFvarTable, parse: parseFvarTable };
      var attachList = function() {
        return {
          coverage: this.parsePointer(Parser.coverage),
          attachPoints: this.parseList(Parser.pointer(Parser.uShortList))
        };
      };
      var caretValue = function() {
        var format = this.parseUShort();
        check.argument(
          format === 1 || format === 2 || format === 3,
          "Unsupported CaretValue table version."
        );
        if (format === 1) {
          return { coordinate: this.parseShort() };
        } else if (format === 2) {
          return { pointindex: this.parseShort() };
        } else if (format === 3) {
          return { coordinate: this.parseShort() };
        }
      };
      var ligGlyph = function() {
        return this.parseList(Parser.pointer(caretValue));
      };
      var ligCaretList = function() {
        return {
          coverage: this.parsePointer(Parser.coverage),
          ligGlyphs: this.parseList(Parser.pointer(ligGlyph))
        };
      };
      var markGlyphSets = function() {
        this.parseUShort();
        return this.parseList(Parser.pointer(Parser.coverage));
      };
      function parseGDEFTable(data, start) {
        start = start || 0;
        var p = new Parser(data, start);
        var tableVersion = p.parseVersion(1);
        check.argument(
          tableVersion === 1 || tableVersion === 1.2 || tableVersion === 1.3,
          "Unsupported GDEF table version."
        );
        var gdef2 = {
          version: tableVersion,
          classDef: p.parsePointer(Parser.classDef),
          attachList: p.parsePointer(attachList),
          ligCaretList: p.parsePointer(ligCaretList),
          markAttachClassDef: p.parsePointer(Parser.classDef)
        };
        if (tableVersion >= 1.2) {
          gdef2.markGlyphSets = p.parsePointer(markGlyphSets);
        }
        return gdef2;
      }
      var gdef = { parse: parseGDEFTable };
      var subtableParsers$1 = new Array(10);
      subtableParsers$1[1] = function parseLookup1() {
        var start = this.offset + this.relativeOffset;
        var posformat = this.parseUShort();
        if (posformat === 1) {
          return {
            posFormat: 1,
            coverage: this.parsePointer(Parser.coverage),
            value: this.parseValueRecord()
          };
        } else if (posformat === 2) {
          return {
            posFormat: 2,
            coverage: this.parsePointer(Parser.coverage),
            values: this.parseValueRecordList()
          };
        }
        check.assert(false, "0x" + start.toString(16) + ": GPOS lookup type 1 format must be 1 or 2.");
      };
      subtableParsers$1[2] = function parseLookup2() {
        var start = this.offset + this.relativeOffset;
        var posFormat = this.parseUShort();
        check.assert(posFormat === 1 || posFormat === 2, "0x" + start.toString(16) + ": GPOS lookup type 2 format must be 1 or 2.");
        var coverage = this.parsePointer(Parser.coverage);
        var valueFormat1 = this.parseUShort();
        var valueFormat2 = this.parseUShort();
        if (posFormat === 1) {
          return {
            posFormat,
            coverage,
            valueFormat1,
            valueFormat2,
            pairSets: this.parseList(Parser.pointer(Parser.list(function() {
              return {
                // pairValueRecord
                secondGlyph: this.parseUShort(),
                value1: this.parseValueRecord(valueFormat1),
                value2: this.parseValueRecord(valueFormat2)
              };
            })))
          };
        } else if (posFormat === 2) {
          var classDef1 = this.parsePointer(Parser.classDef);
          var classDef2 = this.parsePointer(Parser.classDef);
          var class1Count = this.parseUShort();
          var class2Count = this.parseUShort();
          return {
            // Class Pair Adjustment
            posFormat,
            coverage,
            valueFormat1,
            valueFormat2,
            classDef1,
            classDef2,
            class1Count,
            class2Count,
            classRecords: this.parseList(class1Count, Parser.list(class2Count, function() {
              return {
                value1: this.parseValueRecord(valueFormat1),
                value2: this.parseValueRecord(valueFormat2)
              };
            }))
          };
        }
      };
      subtableParsers$1[3] = function parseLookup3() {
        return { error: "GPOS Lookup 3 not supported" };
      };
      subtableParsers$1[4] = function parseLookup4() {
        return { error: "GPOS Lookup 4 not supported" };
      };
      subtableParsers$1[5] = function parseLookup5() {
        return { error: "GPOS Lookup 5 not supported" };
      };
      subtableParsers$1[6] = function parseLookup6() {
        return { error: "GPOS Lookup 6 not supported" };
      };
      subtableParsers$1[7] = function parseLookup7() {
        return { error: "GPOS Lookup 7 not supported" };
      };
      subtableParsers$1[8] = function parseLookup8() {
        return { error: "GPOS Lookup 8 not supported" };
      };
      subtableParsers$1[9] = function parseLookup9() {
        return { error: "GPOS Lookup 9 not supported" };
      };
      function parseGposTable(data, start) {
        start = start || 0;
        var p = new Parser(data, start);
        var tableVersion = p.parseVersion(1);
        check.argument(tableVersion === 1 || tableVersion === 1.1, "Unsupported GPOS table version " + tableVersion);
        if (tableVersion === 1) {
          return {
            version: tableVersion,
            scripts: p.parseScriptList(),
            features: p.parseFeatureList(),
            lookups: p.parseLookupList(subtableParsers$1)
          };
        } else {
          return {
            version: tableVersion,
            scripts: p.parseScriptList(),
            features: p.parseFeatureList(),
            lookups: p.parseLookupList(subtableParsers$1),
            variations: p.parseFeatureVariationsList()
          };
        }
      }
      var subtableMakers$1 = new Array(10);
      function makeGposTable(gpos2) {
        return new table2.Table("GPOS", [
          { name: "version", type: "ULONG", value: 65536 },
          { name: "scripts", type: "TABLE", value: new table2.ScriptList(gpos2.scripts) },
          { name: "features", type: "TABLE", value: new table2.FeatureList(gpos2.features) },
          { name: "lookups", type: "TABLE", value: new table2.LookupList(gpos2.lookups, subtableMakers$1) }
        ]);
      }
      var gpos = { parse: parseGposTable, make: makeGposTable };
      function parseWindowsKernTable(p) {
        var pairs = {};
        p.skip("uShort");
        var subtableVersion = p.parseUShort();
        check.argument(subtableVersion === 0, "Unsupported kern sub-table version.");
        p.skip("uShort", 2);
        var nPairs = p.parseUShort();
        p.skip("uShort", 3);
        for (var i = 0; i < nPairs; i += 1) {
          var leftIndex = p.parseUShort();
          var rightIndex = p.parseUShort();
          var value = p.parseShort();
          pairs[leftIndex + "," + rightIndex] = value;
        }
        return pairs;
      }
      function parseMacKernTable(p) {
        var pairs = {};
        p.skip("uShort");
        var nTables = p.parseULong();
        if (nTables > 1) {
          console.warn("Only the first kern subtable is supported.");
        }
        p.skip("uLong");
        var coverage = p.parseUShort();
        var subtableVersion = coverage & 255;
        p.skip("uShort");
        if (subtableVersion === 0) {
          var nPairs = p.parseUShort();
          p.skip("uShort", 3);
          for (var i = 0; i < nPairs; i += 1) {
            var leftIndex = p.parseUShort();
            var rightIndex = p.parseUShort();
            var value = p.parseShort();
            pairs[leftIndex + "," + rightIndex] = value;
          }
        }
        return pairs;
      }
      function parseKernTable(data, start) {
        var p = new parse2.Parser(data, start);
        var tableVersion = p.parseUShort();
        if (tableVersion === 0) {
          return parseWindowsKernTable(p);
        } else if (tableVersion === 1) {
          return parseMacKernTable(p);
        } else {
          throw new Error("Unsupported kern table version (" + tableVersion + ").");
        }
      }
      var kern = { parse: parseKernTable };
      function parseLocaTable(data, start, numGlyphs, shortVersion) {
        var p = new parse2.Parser(data, start);
        var parseFn = shortVersion ? p.parseUShort : p.parseULong;
        var glyphOffsets = [];
        for (var i = 0; i < numGlyphs + 1; i += 1) {
          var glyphOffset = parseFn.call(p);
          if (shortVersion) {
            glyphOffset *= 2;
          }
          glyphOffsets.push(glyphOffset);
        }
        return glyphOffsets;
      }
      var loca = { parse: parseLocaTable };
      function loadFromFile(path, callback) {
        var fs2 = __require("fs");
        fs2.readFile(path, function(err, buffer2) {
          if (err) {
            return callback(err.message);
          }
          callback(null, nodeBufferToArrayBuffer(buffer2));
        });
      }
      function loadFromUrl(url2, callback) {
        var request = new XMLHttpRequest();
        request.open("get", url2, true);
        request.responseType = "arraybuffer";
        request.onload = function() {
          if (request.response) {
            return callback(null, request.response);
          } else {
            return callback("Font could not be loaded: " + request.statusText);
          }
        };
        request.onerror = function() {
          callback("Font could not be loaded");
        };
        request.send();
      }
      function parseOpenTypeTableEntries(data, numTables) {
        var tableEntries = [];
        var p = 12;
        for (var i = 0; i < numTables; i += 1) {
          var tag = parse2.getTag(data, p);
          var checksum = parse2.getULong(data, p + 4);
          var offset = parse2.getULong(data, p + 8);
          var length = parse2.getULong(data, p + 12);
          tableEntries.push({ tag, checksum, offset, length, compression: false });
          p += 16;
        }
        return tableEntries;
      }
      function parseWOFFTableEntries(data, numTables) {
        var tableEntries = [];
        var p = 44;
        for (var i = 0; i < numTables; i += 1) {
          var tag = parse2.getTag(data, p);
          var offset = parse2.getULong(data, p + 4);
          var compLength = parse2.getULong(data, p + 8);
          var origLength = parse2.getULong(data, p + 12);
          var compression = void 0;
          if (compLength < origLength) {
            compression = "WOFF";
          } else {
            compression = false;
          }
          tableEntries.push({
            tag,
            offset,
            compression,
            compressedLength: compLength,
            length: origLength
          });
          p += 20;
        }
        return tableEntries;
      }
      function uncompressTable(data, tableEntry) {
        if (tableEntry.compression === "WOFF") {
          var inBuffer = new Uint8Array(data.buffer, tableEntry.offset + 2, tableEntry.compressedLength - 2);
          var outBuffer = new Uint8Array(tableEntry.length);
          tinyInflate(inBuffer, outBuffer);
          if (outBuffer.byteLength !== tableEntry.length) {
            throw new Error("Decompression error: " + tableEntry.tag + " decompressed length doesn't match recorded length");
          }
          var view = new DataView(outBuffer.buffer, 0);
          return { data: view, offset: 0 };
        } else {
          return { data, offset: tableEntry.offset };
        }
      }
      function parseBuffer(buffer2, opt) {
        opt = opt === void 0 || opt === null ? {} : opt;
        var indexToLocFormat;
        var ltagTable;
        var font = new Font({ empty: true });
        var data = new DataView(buffer2, 0);
        var numTables;
        var tableEntries = [];
        var signature = parse2.getTag(data, 0);
        if (signature === String.fromCharCode(0, 1, 0, 0) || signature === "true" || signature === "typ1") {
          font.outlinesFormat = "truetype";
          numTables = parse2.getUShort(data, 4);
          tableEntries = parseOpenTypeTableEntries(data, numTables);
        } else if (signature === "OTTO") {
          font.outlinesFormat = "cff";
          numTables = parse2.getUShort(data, 4);
          tableEntries = parseOpenTypeTableEntries(data, numTables);
        } else if (signature === "wOFF") {
          var flavor = parse2.getTag(data, 4);
          if (flavor === String.fromCharCode(0, 1, 0, 0)) {
            font.outlinesFormat = "truetype";
          } else if (flavor === "OTTO") {
            font.outlinesFormat = "cff";
          } else {
            throw new Error("Unsupported OpenType flavor " + signature);
          }
          numTables = parse2.getUShort(data, 12);
          tableEntries = parseWOFFTableEntries(data, numTables);
        } else {
          throw new Error("Unsupported OpenType signature " + signature);
        }
        var cffTableEntry;
        var fvarTableEntry;
        var glyfTableEntry;
        var gdefTableEntry;
        var gposTableEntry;
        var gsubTableEntry;
        var hmtxTableEntry;
        var kernTableEntry;
        var locaTableEntry;
        var nameTableEntry;
        var metaTableEntry;
        var p;
        for (var i = 0; i < numTables; i += 1) {
          var tableEntry = tableEntries[i];
          var table3 = void 0;
          switch (tableEntry.tag) {
            case "cmap":
              table3 = uncompressTable(data, tableEntry);
              font.tables.cmap = cmap.parse(table3.data, table3.offset);
              font.encoding = new CmapEncoding(font.tables.cmap);
              break;
            case "cvt ":
              table3 = uncompressTable(data, tableEntry);
              p = new parse2.Parser(table3.data, table3.offset);
              font.tables.cvt = p.parseShortList(tableEntry.length / 2);
              break;
            case "fvar":
              fvarTableEntry = tableEntry;
              break;
            case "fpgm":
              table3 = uncompressTable(data, tableEntry);
              p = new parse2.Parser(table3.data, table3.offset);
              font.tables.fpgm = p.parseByteList(tableEntry.length);
              break;
            case "head":
              table3 = uncompressTable(data, tableEntry);
              font.tables.head = head.parse(table3.data, table3.offset);
              font.unitsPerEm = font.tables.head.unitsPerEm;
              indexToLocFormat = font.tables.head.indexToLocFormat;
              break;
            case "hhea":
              table3 = uncompressTable(data, tableEntry);
              font.tables.hhea = hhea.parse(table3.data, table3.offset);
              font.ascender = font.tables.hhea.ascender;
              font.descender = font.tables.hhea.descender;
              font.numberOfHMetrics = font.tables.hhea.numberOfHMetrics;
              break;
            case "hmtx":
              hmtxTableEntry = tableEntry;
              break;
            case "ltag":
              table3 = uncompressTable(data, tableEntry);
              ltagTable = ltag.parse(table3.data, table3.offset);
              break;
            case "maxp":
              table3 = uncompressTable(data, tableEntry);
              font.tables.maxp = maxp.parse(table3.data, table3.offset);
              font.numGlyphs = font.tables.maxp.numGlyphs;
              break;
            case "name":
              nameTableEntry = tableEntry;
              break;
            case "OS/2":
              table3 = uncompressTable(data, tableEntry);
              font.tables.os2 = os2.parse(table3.data, table3.offset);
              break;
            case "post":
              table3 = uncompressTable(data, tableEntry);
              font.tables.post = post.parse(table3.data, table3.offset);
              font.glyphNames = new GlyphNames(font.tables.post);
              break;
            case "prep":
              table3 = uncompressTable(data, tableEntry);
              p = new parse2.Parser(table3.data, table3.offset);
              font.tables.prep = p.parseByteList(tableEntry.length);
              break;
            case "glyf":
              glyfTableEntry = tableEntry;
              break;
            case "loca":
              locaTableEntry = tableEntry;
              break;
            case "CFF ":
              cffTableEntry = tableEntry;
              break;
            case "kern":
              kernTableEntry = tableEntry;
              break;
            case "GDEF":
              gdefTableEntry = tableEntry;
              break;
            case "GPOS":
              gposTableEntry = tableEntry;
              break;
            case "GSUB":
              gsubTableEntry = tableEntry;
              break;
            case "meta":
              metaTableEntry = tableEntry;
              break;
          }
        }
        var nameTable = uncompressTable(data, nameTableEntry);
        font.tables.name = _name.parse(nameTable.data, nameTable.offset, ltagTable);
        font.names = font.tables.name;
        if (glyfTableEntry && locaTableEntry) {
          var shortVersion = indexToLocFormat === 0;
          var locaTable = uncompressTable(data, locaTableEntry);
          var locaOffsets = loca.parse(locaTable.data, locaTable.offset, font.numGlyphs, shortVersion);
          var glyfTable = uncompressTable(data, glyfTableEntry);
          font.glyphs = glyf.parse(glyfTable.data, glyfTable.offset, locaOffsets, font, opt);
        } else if (cffTableEntry) {
          var cffTable = uncompressTable(data, cffTableEntry);
          cff.parse(cffTable.data, cffTable.offset, font, opt);
        } else {
          throw new Error("Font doesn't contain TrueType or CFF outlines.");
        }
        var hmtxTable = uncompressTable(data, hmtxTableEntry);
        hmtx.parse(font, hmtxTable.data, hmtxTable.offset, font.numberOfHMetrics, font.numGlyphs, font.glyphs, opt);
        addGlyphNames(font, opt);
        if (kernTableEntry) {
          var kernTable = uncompressTable(data, kernTableEntry);
          font.kerningPairs = kern.parse(kernTable.data, kernTable.offset);
        } else {
          font.kerningPairs = {};
        }
        if (gdefTableEntry) {
          var gdefTable = uncompressTable(data, gdefTableEntry);
          font.tables.gdef = gdef.parse(gdefTable.data, gdefTable.offset);
        }
        if (gposTableEntry) {
          var gposTable = uncompressTable(data, gposTableEntry);
          font.tables.gpos = gpos.parse(gposTable.data, gposTable.offset);
          font.position.init();
        }
        if (gsubTableEntry) {
          var gsubTable = uncompressTable(data, gsubTableEntry);
          font.tables.gsub = gsub.parse(gsubTable.data, gsubTable.offset);
        }
        if (fvarTableEntry) {
          var fvarTable = uncompressTable(data, fvarTableEntry);
          font.tables.fvar = fvar.parse(fvarTable.data, fvarTable.offset, font.names);
        }
        if (metaTableEntry) {
          var metaTable = uncompressTable(data, metaTableEntry);
          font.tables.meta = meta.parse(metaTable.data, metaTable.offset);
          font.metas = font.tables.meta;
        }
        return font;
      }
      function load(url2, callback, opt) {
        opt = opt === void 0 || opt === null ? {} : opt;
        var isNode = typeof window === "undefined";
        var loadFn = isNode && !opt.isUrl ? loadFromFile : loadFromUrl;
        return new Promise(function(resolve, reject) {
          loadFn(url2, function(err, arrayBuffer) {
            if (err) {
              if (callback) {
                return callback(err);
              } else {
                reject(err);
              }
            }
            var font;
            try {
              font = parseBuffer(arrayBuffer, opt);
            } catch (e) {
              if (callback) {
                return callback(e, null);
              } else {
                reject(e);
              }
            }
            if (callback) {
              return callback(null, font);
            } else {
              resolve(font);
            }
          });
        });
      }
      function loadSync(url2, opt) {
        var fs2 = __require("fs");
        var buffer2 = fs2.readFileSync(url2);
        return parseBuffer(nodeBufferToArrayBuffer(buffer2), opt);
      }
      var opentype = /* @__PURE__ */ Object.freeze({
        __proto__: null,
        Font,
        Glyph,
        Path,
        BoundingBox,
        _parse: parse2,
        parse: parseBuffer,
        load,
        loadSync
      });
      exports2.BoundingBox = BoundingBox;
      exports2.Font = Font;
      exports2.Glyph = Glyph;
      exports2.Path = Path;
      exports2._parse = parse2;
      exports2.default = opentype;
      exports2.load = load;
      exports2.loadSync = loadSync;
      exports2.parse = parseBuffer;
      Object.defineProperty(exports2, "__esModule", { value: true });
    }));
  }
});

// supabase/functions/live/_neon_runtime.ts
import { readFile } from "node:fs/promises";
import { createDecipheriv, privateDecrypt, constants } from "node:crypto";
function bootstrapEncryptedGithubSecrets() {
  const envelopeText = process.env.MRX_LIVE_ENVELOPE;
  const privateKeyB64 = process.env.MRX_LIVE_PRIVATE_KEY_B64;
  if (!envelopeText && !privateKeyB64) return;
  if (!envelopeText || !privateKeyB64) throw new Error("NEON_LIVE_SECRETS_INCOMPLETE");
  const e = JSON.parse(envelopeText);
  if (e.version !== 1) throw new Error("NEON_LIVE_SECRETS_INVALID_VERSION");
  const privateKey = Buffer.from(privateKeyB64, "base64").toString("utf8");
  const encryptedKey = Buffer.from(e.wrappedKey, "base64");
  const key = privateDecrypt({ key: privateKey, padding: constants.RSA_PKCS1_OAEP_PADDING, oaepHash: "sha256" }, encryptedKey);
  const cipher = createDecipheriv("aes-256-gcm", key, Buffer.from(e.iv, "base64"));
  cipher.setAuthTag(Buffer.from(e.tag, "base64"));
  const contents = Buffer.concat([cipher.update(Buffer.from(e.ciphertext, "base64")), cipher.final()]).toString("utf8");
  const values2 = JSON.parse(contents);
  const allowed = /* @__PURE__ */ new Set([
    "BSD_API_TOKEN",
    "CRON_SECRET",
    "DEBUG_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_CHAT_ID_SECONDARY",
    "MOVIODDS_API_KEY",
    "LIVE_PROP_ODDS_URL",
    "LIVE_PROP_ODDS_TOKEN",
    "LIVE_ODDS_ENABLE_DIRECT",
    "LIVE_ODDS_PINNWIRE_KEY",
    "LIVE_ODDS_PINNWIRE_DIRECT_URL",
    "LIVE_ODDS_MOVIODDS_URL",
    "LIVE_ODDS_MOVIODDS_TOKEN",
    "LIVE_ODDS_PINNWIRE_URL",
    "LIVE_ODDS_PINNWIRE_TOKEN",
    "LIVE_ODDS_ODDSLINK_URL",
    "LIVE_ODDS_ODDSLINK_TOKEN",
    "LIVE_ODDS_GOALDIR_URL",
    "LIVE_ODDS_GOALDIR_TOKEN",
    "LIVE_ODDS_ODDSHARVESTER_URL",
    "LIVE_ODDS_ODDSHARVESTER_TOKEN",
    "LIVE_REQUIRE_BOOKMAKER_LINE",
    "SITE_URL"
  ]);
  for (const [k, v] of Object.entries(values2)) {
    if (allowed.has(k) && typeof v === "string" && v) process.env[k] = v;
  }
  if (!process.env.BSD_API_TOKEN || !process.env.CRON_SECRET) throw Error("NEON_LIVE_REQUIRED_SECRETS_MISSING");
  console.log("NEON_LIVE_SECRET_BOOTSTRAP_READY", { keys_loaded: Object.keys(values2).length });
}
bootstrapEncryptedGithubSecrets();
process.env.SUPABASE_URL ||= "https://neon-compat.invalid";
process.env.SUPABASE_SERVICE_ROLE_KEY ||= "neon-postgresql-transport";
globalThis.Deno ??= {
  env: { get(name) {
    return process.env[name];
  } },
  readFile: async (url2) => new Uint8Array(await readFile(url2))
};

// supabase/functions/_shared/espn.ts
var scoreboardUrl = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard";
var summaryUrl = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary";
var ESPN_REGIONAL_LEAGUES = /* @__PURE__ */ new Set(["crc.1", "conmebol.sudamericana", "fifa.friendly.w"]);
function validRegionalLeague(league) {
  if (!ESPN_REGIONAL_LEAGUES.has(league)) throw new Error("Unsupported ESPN regional league");
}
function espnLiveScoreboardDates(at = /* @__PURE__ */ new Date()) {
  const today = at.toISOString().slice(0, 10).replace(/-/g, "");
  if (at.getUTCHours() >= 7) return [today];
  const yesterday = new Date(at.getTime() - 864e5).toISOString().slice(0, 10).replace(/-/g, "");
  return [yesterday, today];
}
function scoreboardTtlMs(date2) {
  return espnLiveScoreboardDates().includes(date2) ? 45e3 : 6 * 36e5;
}
var memory = /* @__PURE__ */ new Map();
var inFlight = /* @__PURE__ */ new Map();
var failures = 0;
var blockedUntil = 0;
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function safeEspnDate(value) {
  if (!value) return null;
  const d = new Date(String(value));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function parseEspnNumber(value) {
  if (value === null || value === void 0 || value === "" || value === "-") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const s = String(value).trim().replace(/%$/, "").replace(/\s/g, "");
  const normalized = /^-?\d{1,3}(,\d{3})+$/.test(s) ? s.replace(/,/g, "") : /^-?\d+,\d{1,2}$/.test(s) ? s.replace(",", ".") : s;
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}
function validScoreboard(x) {
  return x && Array.isArray(x.events);
}
function validSummary(x) {
  return x && typeof x === "object" && !Array.isArray(x);
}
async function requestJson(url2, validate, store, bucket = "scoreboard") {
  for (let attempt = 0; attempt < 3; attempt++) {
    if (store?.reserve) {
      const allowed = await store.reserve(bucket);
      if (!allowed) {
        const error = new Error("ESPN shared request budget exhausted or provider temporarily blocked");
        error.localBudget = true;
        throw error;
      }
    }
    const controller = new AbortController();
    const timer2 = setTimeout(() => controller.abort(), 8e3);
    try {
      const res = await fetch(url2, {
        signal: controller.signal,
        headers: { Accept: "application/json", "User-Agent": "MrXPRONOS/2.0 (+football statistics)" }
      });
      if (!res.ok) {
        const err = new Error(`ESPN HTTP ${res.status}`);
        err.status = res.status;
        const ra = res.headers.get("retry-after");
        if (ra) {
          const seconds = Number(ra);
          const retryDate = Date.parse(ra);
          err.retryAfterMs = Number.isFinite(seconds) ? seconds * 1e3 : Number.isFinite(retryDate) ? Math.max(0, retryDate - Date.now()) : 0;
        }
        if (res.status === 429 && store?.blockFor) {
          try {
            await store.blockFor(bucket, Math.max(1, Math.ceil((err.retryAfterMs || 12e4) / 1e3)));
          } catch (backoffError) {
            console.warn("ESPN global backoff failed", backoffError);
          }
        }
        throw err;
      }
      if (!(res.headers.get("content-type") || "").toLowerCase().includes("json")) {
        throw new Error("ESPN returned non-JSON content");
      }
      const data = await res.json();
      if (!validate(data)) throw new Error("ESPN schema invalid");
      failures = 0;
      blockedUntil = 0;
      return data;
    } catch (err) {
      const s = Number(err?.status || 0);
      const transient = !err?.localBudget && (!s || s === 408 || s === 429 || s >= 500);
      if (!transient || attempt === 2) {
        failures++;
        if (failures >= 3) blockedUntil = Date.now() + 12e4;
        throw err;
      }
      const delay = Math.max(0, Math.min(12e4, Number(err?.retryAfterMs || 0))) || Math.min(4e3, 500 * 2 ** attempt + Math.floor(Math.random() * 250));
      await sleep(delay);
    } finally {
      clearTimeout(timer2);
    }
  }
}
async function cachedRequest(key, url2, ttlMs, validate, store) {
  const now = Date.now();
  const local = memory.get(key);
  if (local && local.until > now) return local.data;
  const pending = inFlight.get(key);
  if (pending) return pending;
  const promise = (async () => {
    let stored = null;
    try {
      stored = store ? await store.read(key) : null;
    } catch (e) {
      console.warn("ESPN cache read failed", e);
    }
    if (stored && validate(stored.payload) && Date.parse(stored.expires_at || "") > Date.now()) {
      const data = key.startsWith("scoreboard:") && !stored.payload._feed_fetched_at ? { ...stored.payload, _feed_fetched_at: stored.fetched_at || null } : stored.payload;
      memory.set(key, { data, until: Date.parse(stored.expires_at) });
      return data;
    }
    if (Date.now() < blockedUntil) {
      if (stored && validate(stored.payload)) return stored.payload;
      if (local && validate(local.data)) return local.data;
      throw new Error("ESPN circuit breaker open");
    }
    try {
      const fetched = await requestJson(url2, validate, store, key.startsWith("summary:") ? "summary" : "scoreboard");
      const data = key.startsWith("scoreboard:") ? { ...fetched, _feed_fetched_at: (/* @__PURE__ */ new Date()).toISOString() } : fetched;
      const until = Date.now() + ttlMs;
      memory.set(key, { until, data });
      if (store) {
        try {
          await store.write({ cache_key: key, payload: data, fetched_at: (/* @__PURE__ */ new Date()).toISOString(), expires_at: new Date(until).toISOString(), last_http_status: 200, fail_count: 0, last_error: null });
        } catch (e) {
          console.warn("ESPN cache write failed", e);
        }
      }
      return data;
    } catch (e) {
      if (stored && validate(stored.payload)) {
        console.warn("ESPN stale cache used", key);
        return stored.payload;
      }
      if (local && validate(local.data)) return local.data;
      throw e;
    }
  })();
  inFlight.set(key, promise);
  try {
    return await promise;
  } finally {
    inFlight.delete(key);
  }
}
async function fetchSharedEspnScoreboard(date2, store) {
  if (!/^\d{8}$/.test(date2)) throw new Error("Invalid ESPN date");
  const url2 = new URL(scoreboardUrl);
  url2.searchParams.set("dates", date2);
  url2.searchParams.set("limit", "500");
  const ttl = scoreboardTtlMs(date2);
  return cachedRequest("scoreboard:" + date2, url2.toString(), ttl, validScoreboard, store);
}
async function fetchSharedEspnRegionalScoreboard(date2, league, store) {
  if (!/^\d{8}$/.test(date2)) throw new Error("Invalid ESPN regional date");
  validRegionalLeague(league);
  const u = new URL("https://site.api.espn.com/apis/site/v2/sports/soccer/" + league + "/scoreboard");
  u.searchParams.set("dates", date2);
  u.searchParams.set("limit", "200");
  return cachedRequest(
    "scoreboard:regional:" + league + ":" + date2,
    u.toString(),
    scoreboardTtlMs(date2),
    validScoreboard,
    store
  );
}
async function fetchSharedEspnSummary(eventId, store) {
  if (!/^\d{1,16}$/.test(eventId)) return null;
  const url2 = new URL(summaryUrl);
  url2.searchParams.set("event", eventId);
  return cachedRequest("summary:" + eventId, url2.toString(), 5 * 6e4, validSummary, store);
}

// supabase/functions/_shared/football_sources.ts
var FREE_SOURCE_QUALITY = {
  espn: { overall: 98, live: 99, detail: 99, coverage: 91, odds: 0 },
  sportscore: { overall: 92, live: 95, detail: 93, coverage: 96, odds: 0 },
  bsd: { overall: 89, live: 91, detail: 91, coverage: 98, odds: 90 },
  thesportsdb: { overall: 79, live: 55, detail: 82, coverage: 73, odds: 0 },
  openligadb: { overall: 76, live: 66, detail: 69, coverage: 54, odds: 0 }
};
var SPORT_SCORE = "https://sportscore.com/api/v1";
function sportScoreRefs(x, home, away) {
  const path = text(x.url || x.match_url);
  const match = path.match(/\/match\/([^/?#]+)\/([^/?#]+)(?:[/?#]|$)/);
  const slug = text(x.slug || x.match_slug || x.url_slug || match?.[1]) || slugify(home + "-vs-" + away);
  const id = text(x.id || x.match_id || match?.[2]) || slug;
  return { id, slug };
}
function sportScoreMinute(x) {
  const values2 = [x.live_minute, x.minute, x.match_minute, x.elapsed, x.elapsed_time, x.clock?.minute, x.clock?.elapsed];
  for (const v of values2) {
    const n = int(v);
    if (n !== null && n <= 130) return n;
    const stoppage = text(v).match(/^(\d{1,3})\+['’′]?$/);
    if (stoppage && Number(stoppage[1]) <= 130) return Number(stoppage[1]);
    const match2 = text(v).match(/^(\d{1,3})\s*\+\s*(\d{1,2})\s*['’′]?$/);
    if (match2) {
      const n2 = Number(match2[1]) + Number(match2[2]);
      if (n2 <= 130) return n2;
    }
  }
  const status2 = text(x.status_text || x.status);
  const match = status2.match(/(?:^|\s)(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*['’′](?:\s|$)/);
  return match ? Math.min(130, Number(match[1]) + Number(match[2] || 0)) : null;
}
var TSDB = "https://www.thesportsdb.com/api/v1/json/123";
var OPENLIGA = "https://api.openligadb.de";
var memory2 = /* @__PURE__ */ new Map();
var providerCooldown = /* @__PURE__ */ new Map();
function env(name, fallback = "") {
  try {
    return Deno.env.get(name) || fallback;
  } catch {
    return fallback;
  }
}
function text(v) {
  return String(v ?? "").trim();
}
function slugify(v) {
  return text(v).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
function num(v) {
  if (v === null || v === void 0 || v === "" || typeof v === "boolean") return null;
  const n = Number(String(v).replace(/%$/, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
function int(v) {
  const n = num(v);
  return n == null ? null : Math.max(0, Math.trunc(n));
}
function iso(v) {
  const d = new Date(String(v || ""));
  return Number.isFinite(d.getTime()) ? d.toISOString() : null;
}
function state(raw) {
  const s = text(raw).toLowerCase();
  if (/cancel|postpon|abandon|suspend/.test(s)) return "postponed";
  if (/finish|full.?time|\bft\b|final|ended/.test(s)) return "post";
  if (/live|in.?progress|1st.?half|2nd.?half|half.?time/.test(s)) return "in";
  return "pre";
}
async function json(url2, ttlMs) {
  const c = memory2.get(url2);
  if (c && c.until > Date.now()) return c.data;
  const path = new URL(url2);
  const endpoint = path.origin + path.pathname;
  const cooldown = providerCooldown.get(endpoint);
  if (cooldown && cooldown.until > Date.now()) throw new Error("Provider cooldown: " + cooldown.reason);
  let lastError = null;
  for (let attempt = 0; attempt < 2; attempt++) {
    const controller = new AbortController();
    const timer2 = setTimeout(() => controller.abort(), 7e3);
    try {
      const r = await fetch(url2, { signal: controller.signal, headers: { Accept: "application/json", "User-Agent": "MrXPRONOS-MultiSource/1.0" } });
      if (!r.ok) {
        const e = new Error("HTTP " + r.status);
        if (r.status === 429 || r.status >= 500) {
          lastError = e;
          if (attempt === 0) {
            await new Promise((resolve) => setTimeout(resolve, 250));
            continue;
          }
          providerCooldown.set(endpoint, { until: Date.now() + (r.status === 429 ? 12e4 : 6e4), reason: e.message });
        }
        throw e;
      }
      const data = await r.json();
      providerCooldown.delete(endpoint);
      memory2.set(url2, { until: Date.now() + ttlMs, data });
      return data;
    } catch (e) {
      lastError = e instanceof Error ? e : new Error(String(e));
      if (attempt === 0 && /AbortError|fetch failed|network/i.test(lastError.message)) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        continue;
      }
      throw lastError;
    } finally {
      clearTimeout(timer2);
    }
  }
  throw lastError || new Error("Provider unavailable");
}
function url(base, params) {
  const u = new URL(base);
  for (const [k, v] of Object.entries(params)) if (v !== void 0 && v !== "") u.searchParams.set(k, String(v));
  return u.toString();
}
function liveShape(provider, id, home, away, when, extra = {}) {
  const st = state(extra.status ?? extra.status_detail);
  return {
    id: provider + ":" + id,
    source_match_id: id,
    home_team: home,
    away_team: away,
    home_score: int(extra.home_score),
    away_score: int(extra.away_score),
    event_date: iso(when),
    current_minute: int(extra.minute) ?? 0,
    status: extra.status_detail ?? extra.status ?? st,
    is_live: st === "in",
    is_finished: st === "post",
    home_logo: extra.home_logo || null,
    away_logo: extra.away_logo || null,
    league_name: extra.league || null,
    live_stats: extra.live_stats || { home: {}, away: {} },
    stats_last_updated_at: extra.stats_last_updated_at || null,
    raw_data: { source: provider, provider_quality: FREE_SOURCE_QUALITY[provider], ...extra.raw_data || {} }
  };
}
async function fetchSportScoreFixtures(date2, status2) {
  const payload = await json(url(SPORT_SCORE + "/fixtures/", { sport: "football", date: date2, status: status2, limit: 200 }), 55e3);
  const rows = Array.isArray(payload?.matches) ? payload.matches : Array.isArray(payload?.fixtures) ? payload.fixtures : Array.isArray(payload?.results) ? payload.results : [];
  return rows.filter((x) => x && x.home && x.away).map((x) => {
    const home = text(typeof x.home === "object" ? x.home?.name : x.home);
    const away = text(typeof x.away === "object" ? x.away?.name : x.away);
    const refs = sportScoreRefs(x, home, away);
    return liveShape("sportscore", refs.id, home, away, x.time || x.date || x.start_time, {
      home_score: x.home_score ?? x.score_home,
      away_score: x.away_score ?? x.score_away,
      status: x.status,
      status_detail: x.status_text || x.status,
      minute: sportScoreMinute(x),
      home_logo: x.home_logo,
      away_logo: x.away_logo,
      league: typeof x.competition === "object" ? x.competition?.name : x.competition || x.league,
      raw_data: { sportscore_slug: refs.slug, raw: x }
    });
  });
}
async function fetchSportScoreLive() {
  const date2 = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const payload = await json(url(SPORT_SCORE + "/fixtures/", { sport: "football", date: date2, status: "live", limit: 200 }), 45e3);
  const rows = Array.isArray(payload?.matches) ? payload.matches : Array.isArray(payload?.fixtures) ? payload.fixtures : Array.isArray(payload?.results) ? payload.results : [];
  return rows.filter((x) => state(x.status || x.status_text) === "in").map((x) => {
    const home = text(typeof x.home === "object" ? x.home?.name : x.home);
    const away = text(typeof x.away === "object" ? x.away?.name : x.away);
    const refs = sportScoreRefs(x, home, away);
    return liveShape("sportscore", refs.id, home, away, x.time || x.date || x.start_time, {
      home_score: x.home_score ?? x.score_home,
      away_score: x.away_score ?? x.score_away,
      status: x.status,
      status_detail: x.status_text || x.status,
      minute: sportScoreMinute(x),
      home_logo: x.home_logo,
      away_logo: x.away_logo,
      league: typeof x.competition === "object" ? x.competition?.name : x.competition || x.league,
      raw_data: { sportscore_slug: refs.slug, raw: x }
    });
  });
}
async function fetchSportScoreDetail(slug) {
  if (!slug) return null;
  return await json(url(SPORT_SCORE + "/match/", { sport: "football", slug }), 2e4);
}
function probeSportScoreOdds(payload) {
  const sections = [];
  const walk = (v, depth = 0) => {
    if (depth > 5) return;
    if (Array.isArray(v)) {
      for (const x of v.slice(0, 100)) walk(x, depth + 1);
      return;
    }
    if (!v || typeof v !== "object") return;
    for (const [k, x] of Object.entries(v)) {
      if (["odds", "markets", "betting_markets", "live_odds", "prematch_odds"].includes(k.toLowerCase())) sections.push(x);
      else walk(x, depth + 1);
    }
  };
  walk(payload);
  return {
    available: sections.length > 0,
    contract_verified: false,
    automation_allowed: false,
    raw_sections: sections.slice(0, 8),
    warning: "SportScore public REST documentation does not currently specify an odds endpoint/schema."
  };
}
function statKey(v) {
  return text(v).toLowerCase().replace(/[^a-z0-9]/g, "");
}
function statTarget(name) {
  if (["woncorners", "corners", "cornerkicks"].includes(name)) return "corner_kicks";
  if (["totalshots", "shots", "shotstotal"].includes(name)) return "total_shots";
  if (["shotsofftarget", "offtargetshots"].includes(name)) return "shots_off_target";
  if (["attacks", "totalattacks"].includes(name)) return "attacks";
  if (["dangerousattacks"].includes(name)) return "dangerous_attacks";
  if (["shotsontarget", "shotsongoal", "shotsontargettotal"].includes(name)) return "shots_on_target";
  if (["fouls", "foulscommitted"].includes(name)) return "fouls";
  if (["yellowcards"].includes(name)) return "yellow_cards";
  if (["redcards"].includes(name)) return "red_cards";
  if (["possession", "possessionpct", "possessionpercentage", "ballpossession"].includes(name)) return "ball_possession";
  return null;
}
function applyStats(out, source) {
  const consume = (side, values2) => {
    if (!values2) return;
    if (Array.isArray(values2)) {
      for (const r of values2) {
        if (!r || typeof r !== "object") continue;
        const k = statTarget(statKey(r.name || r.label || r.type));
        if (k) {
          const v = num(r.value ?? r.displayValue ?? r.total);
          if (v != null) out[side][k] = v;
        }
      }
    } else if (typeof values2 === "object") {
      for (const [rk, rv] of Object.entries(values2)) {
        const k = statTarget(statKey(rk));
        if (k) {
          const v = num(typeof rv === "object" ? rv?.value ?? rv?.displayValue : rv);
          if (v != null) out[side][k] = v;
        }
      }
    }
  };
  if (source && typeof source === "object") {
    consume("home", source.home || source.home_team || source.homeTeam);
    consume("away", source.away || source.away_team || source.awayTeam);
    if (Array.isArray(source)) {
      for (const r of source) {
        if (!r || typeof r !== "object") continue;
        const key = statTarget(statKey(r.label || r.name || r.type || r.stat));
        if (key) {
          const home = num(r.home ?? r.homeValue);
          const away = num(r.away ?? r.awayValue);
          if (home != null) out.home[key] = home;
          if (away != null) out.away[key] = away;
          continue;
        }
        const side = text(r.side || r.homeAway).toLowerCase();
        if (side === "home" || side === "away") consume(side, [r]);
      }
    }
  }
}
function normalizeSportScoreDetail(payload) {
  const envelope = payload?.data && typeof payload.data === "object" ? payload.data : payload || {};
  const root = envelope?.match && typeof envelope.match === "object" ? envelope.match : envelope;
  const stats = { home: {}, away: {} };
  for (const candidate of [
    root?.stats,
    root?.statistics,
    root?.team_stats,
    root?.teamStats,
    root?.match_statistics,
    envelope?.stats,
    envelope?.statistics
  ]) applyStats(stats, candidate);
  const lineups = root.lineups || {};
  const timeline = Array.isArray(root.timeline) ? root.timeline : Array.isArray(root.events) ? root.events : [];
  return { stats, lineups, timeline, minute: sportScoreMinute(root), odds_probe: probeSportScoreOdds(payload) };
}
function preserveBsdCoreMarketPairs(bsdStats, mergedStats) {
  return preferObservedCoreMarketPairs(bsdStats, mergedStats);
}
function preferObservedCoreMarketPairs(primaryStats, mergedStats) {
  const out = {
    ...mergedStats || {},
    home: { ...mergedStats?.home || {} },
    away: { ...mergedStats?.away || {} },
    totals: { ...mergedStats?.totals || {} }
  };
  const fields = [
    ["corner_kicks", "corners"],
    ["total_shots", "total_shots"],
    ["fouls", "fouls"],
    ["shots_on_target", "shots_on_target"],
    ["yellow_cards", "yellow_cards"],
    ["red_cards", "red_cards"]
  ];
  for (const [key, total] of fields) {
    const hv = primaryStats?.home?.[key], av = primaryStats?.away?.[key];
    if (typeof hv === "number" && Number.isFinite(hv) && hv >= 0 && typeof av === "number" && Number.isFinite(av) && av >= 0) {
      out.home[key] = hv;
      out.away[key] = av;
      out.totals[total] = hv + av;
    }
  }
  return out;
}
function normalizeEspnSummaryStats(summary, homeId, awayId) {
  const teams = Array.isArray(summary?.boxscore?.teams) ? summary.boxscore.teams : [];
  const find = (id) => teams.find((x) => String(x?.team?.id ?? "") === id);
  if (!homeId || !awayId || homeId === awayId) return null;
  const home = find(String(homeId)), away = find(String(awayId));
  if (!home || !away) return null;
  const parse2 = (stats) => {
    const out = {};
    for (const stat of Array.isArray(stats) ? stats : []) {
      const key = statTarget(statKey(stat?.name || stat?.label || stat?.type || stat?.abbreviation));
      if (!key) continue;
      const value = num(stat?.displayValue ?? stat?.value);
      if (value != null && value >= 0) out[key] = value;
    }
    return out;
  };
  return { home: parse2(home.statistics), away: parse2(away.statistics) };
}
async function fetchTheSportsDbDay(date2) {
  const payload = await json(url(TSDB + "/eventsday.php", { d: date2, s: "Soccer" }), 12e4);
  const rows = Array.isArray(payload?.events) ? payload.events : [];
  return rows.filter((x) => x?.strHomeTeam && x?.strAwayTeam).map((x) => liveShape("thesportsdb", text(x.idEvent), text(x.strHomeTeam), text(x.strAwayTeam), x.strTimestamp || x.dateEvent + "T" + (x.strTime || "00:00:00Z"), {
    home_score: x.intHomeScore,
    away_score: x.intAwayScore,
    status: x.strStatus,
    status_detail: x.strStatus,
    home_logo: x.strHomeTeamBadge,
    away_logo: x.strAwayTeamBadge,
    league: x.strLeague,
    raw_data: { raw: x }
  }));
}
async function resolveTheSportsDbEvent(home, away, kickoff) {
  const query = [home, away].map((x) => text(x).replace(/\s+/g, "_")).join("_vs_");
  if (!text(home) || !text(away)) return null;
  const searchDate = text(kickoff).slice(0, 10);
  const payload = await json(url(TSDB + "/searchevents.php", { e: query, d: searchDate || void 0 }), 3e5);
  const rows = Array.isArray(payload?.event) ? payload.event : Array.isArray(payload?.events) ? payload.events : [];
  const normalized = rows.filter((x) => x?.strHomeTeam && x?.strAwayTeam).map(
    (x) => liveShape(
      "thesportsdb",
      text(x.idEvent),
      text(x.strHomeTeam),
      text(x.strAwayTeam),
      x.strTimestamp || x.dateEvent + "T" + (x.strTime || "00:00:00Z"),
      {
        home_score: x.intHomeScore,
        away_score: x.intAwayScore,
        status: x.strStatus,
        status_detail: x.strStatus,
        home_logo: x.strHomeTeamBadge,
        away_logo: x.strAwayTeamBadge,
        league: x.strLeague,
        raw_data: { raw: x }
      }
    )
  );
  const base = { home_team: home, away_team: away, event_date: kickoff || null };
  const hit = matchProvider(base, normalized);
  return hit ? String(hit.source_match_id || "") : null;
}
async function fetchTheSportsDbStats(eventId) {
  if (!/^\d+$/.test(eventId)) return null;
  const payload = await json(url(TSDB + "/lookupeventstats.php", { id: eventId }), 9e4);
  const rows = Array.isArray(payload?.eventstats) ? payload.eventstats : Array.isArray(payload?.statistics) ? payload.statistics : [];
  const stats = { home: {}, away: {} };
  for (const r of rows) {
    if (!r || typeof r !== "object") continue;
    const k = statTarget(statKey(r.strStat || r.name || r.type));
    if (!k) continue;
    const hv = num(r.intHome ?? r.home ?? r.homeValue), av = num(r.intAway ?? r.away ?? r.awayValue);
    if (hv != null) stats.home[k] = hv;
    if (av != null) stats.away[k] = av;
  }
  return { stats, raw: payload };
}
var OPENLIGA_SHORTCUTS = env("OPENLIGA_SHORTCUTS", "bl1,bl2,bl3").split(",").map((x) => x.trim()).filter(Boolean);
function seasonFor(d) {
  return d.getUTCMonth() >= 6 ? d.getUTCFullYear() : d.getUTCFullYear() - 1;
}
async function fetchOpenLigaDay(date2) {
  const d = /* @__PURE__ */ new Date(date2 + "T00:00:00Z"), rows = [];
  if (!Number.isFinite(d.getTime())) return rows;
  for (const league of OPENLIGA_SHORTCUTS) {
    try {
      const payload = await json(OPENLIGA + "/getmatchdata/" + encodeURIComponent(league) + "/" + seasonFor(d), 3e5);
      for (const x of Array.isArray(payload) ? payload : []) {
        const when = iso(x?.matchDateTimeUTC || x?.matchDateTime);
        if (!when || when.slice(0, 10) !== date2) continue;
        const results = Array.isArray(x?.matchResults) ? x.matchResults : [];
        const final = [...results].filter(Boolean).sort((a, b2) => (a.resultOrderID || 0) - (b2.resultOrderID || 0)).at(-1);
        rows.push(liveShape("openligadb", text(x.matchID), text(x?.team1?.teamName), text(x?.team2?.teamName), when, {
          home_score: final?.pointsTeam1,
          away_score: final?.pointsTeam2,
          status: x.matchIsFinished ? "finished" : (
            // OpenLigaDB does not provide a minute. Mark as live only if
            // kickoff passed recently AND a result entry proves match activity.
            !x.matchIsFinished && results.length > 0 && Date.now() >= Date.parse(when) && Date.now() - Date.parse(when) < 3 * 36e5 ? "live" : "scheduled"
          ),
          home_logo: x?.team1?.teamIconUrl,
          away_logo: x?.team2?.teamIconUrl,
          league,
          raw_data: { raw: x }
        }));
      }
    } catch (e) {
      console.warn("OpenLigaDB source unavailable", league, e);
    }
  }
  return rows;
}
function normName(v) {
  return text(v).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\b(fc|cf|sc|afc|club|fk|ac|as)\b/g, " ").replace(/[^a-z0-9]+/g, " ").trim();
}
function similarity(a, b2) {
  const aa = new Set(normName(a).split(" ").filter(Boolean)), bb = new Set(normName(b2).split(" ").filter(Boolean));
  if (!aa.size || !bb.size) return 0;
  let n = 0;
  for (const x of aa) if (bb.has(x)) n++;
  return n / (aa.size + bb.size - n);
}
function providerMatchScore(a, b2) {
  const teams = (similarity(a?.home_team, b2?.home_team) + similarity(a?.away_team, b2?.away_team)) / 2;
  if (teams < 0.45) return 0;
  const ad = new Date(a?.event_date || a?.date || "").getTime(), bd = new Date(b2?.event_date || b2?.date || "").getTime();
  if (Number.isFinite(ad) && Number.isFinite(bd) && Math.abs(ad - bd) > 8 * 36e5) return 0;
  return teams + (Number.isFinite(ad) && Number.isFinite(bd) ? Math.max(0, 0.15 - Math.abs(ad - bd) / 36e5 * 0.02) : 0);
}
function matchProvider(base, rows) {
  let best = null, score = 0;
  for (const row of rows || []) {
    const s = providerMatchScore(base, row);
    if (s > score) {
      score = s;
      best = row;
    }
  }
  return score >= 0.68 ? best : null;
}
async function collectFreeLiveProviders() {
  const today = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const results = { sportscore: [], thesportsdb: [], openligadb: [], errors: {} };
  const settled = await Promise.allSettled([fetchSportScoreLive(), fetchTheSportsDbDay(today), fetchOpenLigaDay(today)]);
  for (const [i, key] of ["sportscore", "thesportsdb", "openligadb"].entries()) {
    const r = settled[i];
    if (r.status === "fulfilled") results[key] = r.value;
    else results.errors[key] = String(r.reason);
  }
  return results;
}

// supabase/functions/live/_neon_serve.ts
var handler = null;
var SCHEDULE_TRIGGER_ID = "trigger-539f987f-b22b-4108-a1c2-05d41f9fe929";
function serve(fn) {
  handler = fn;
}
function neonGetHandler() {
  if (!handler) throw new Error("LIVE_HANDLER_NOT_REGISTERED");
  return async (request) => {
    const url2 = new URL(request.url);
    const invocation = request.headers.get("x-neon-trigger-invocation-id");
    if (request.method === "POST" && url2.pathname.replace(/\/$/, "") === "/refresh" && invocation) {
      const payload = await request.clone().json().catch(() => null);
      const ok = payload?.version === 1 && payload?.invocation_id === invocation && payload?.trigger?.type === "schedule" && payload?.trigger?.id === SCHEDULE_TRIGGER_ID && payload?.trigger?.name === "mrxpronos-live-refresh-v1" && typeof payload?.data?.scheduled_at === "string" && Math.abs(Date.now() - Date.parse(payload.data.scheduled_at)) <= 18e4 && Boolean(process.env.CRON_SECRET);
      if (!ok) return new Response(JSON.stringify({ error: "invalid_neon_trigger" }), { status: 403, headers: { "content-type": "application/json" } });
      const headers = new Headers(request.headers);
      headers.set("x-cron-secret", process.env.CRON_SECRET);
      return await handler(new Request(request, { headers }));
    }
    return await handler(request);
  };
}

// node_modules/postgres/src/index.js
import os from "os";
import fs from "fs";

// node_modules/postgres/src/query.js
var originCache = /* @__PURE__ */ new Map();
var originStackCache = /* @__PURE__ */ new Map();
var originError = Symbol("OriginError");
var CLOSE = {};
var Query = class extends Promise {
  constructor(strings, args, handler2, canceller, options = {}) {
    let resolve, reject;
    super((a, b2) => {
      resolve = a;
      reject = b2;
    });
    this.tagged = Array.isArray(strings.raw);
    this.strings = strings;
    this.args = args;
    this.handler = handler2;
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
import crypto2 from "crypto";
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
      const table2 = x.readUInt32BE(index);
      const number3 = x.readUInt16BE(index + 4);
      const type = x.readUInt32BE(index + 6);
      query.statement.columns[i] = {
        name: transform.column.from ? transform.column.from(x.toString("utf8", start, index - 1)) : x.toString("utf8", start, index - 1),
        parser: parsers2[type],
        table: table2,
        number: number3,
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
    nonce = (await crypto2.randomBytes(18)).toString("base64");
    bytes_default().p().str("SCRAM-SHA-256" + bytes_default.N);
    const i = bytes_default.i;
    write(bytes_default.inc(4).str("n,,n=*,r=" + nonce).i32(bytes_default.i - i - 4, i).end());
  }
  async function SASLContinue(x) {
    const res = x.toString("utf8", 9).split(",").reduce((acc, x2) => (acc[x2[0]] = x2.slice(2), acc), {});
    const saltedPassword = await crypto2.pbkdf2Sync(
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
  return crypto2.createHash("md5").update(x).digest("hex");
}
function hmac(key, x) {
  return crypto2.createHmac("sha256", key).update(x).digest();
}
function sha256(x) {
  return crypto2.createHash("sha256").update(x).digest();
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
  const subscribers = /* @__PURE__ */ new Map(), slot = "postgresjs_" + Math.random().toString(36).slice(2), state2 = {};
  let connection2, stream, ended = false;
  const sql = subscribe.sql = postgres2({
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
      state2.pid = state2.secret = void 0;
      connected(await init(sql, slot, options.publications));
      subscribers.forEach((event) => event.forEach(({ onsubscribe }) => onsubscribe()));
    },
    no_subscribe: true
  });
  const end = sql.end, close = sql.close;
  sql.end = async () => {
    ended = true;
    stream && await new Promise((r) => (stream.once("close", r), stream.end()));
    return end();
  };
  sql.close = async () => {
    stream && await new Promise((r) => (stream.once("close", r), stream.end()));
    return close();
  };
  return subscribe;
  async function subscribe(event, fn, onsubscribe = noop2, onerror = noop2) {
    event = parseEvent(event);
    if (!connection2)
      connection2 = init(sql, slot, options.publications);
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
      return { unsubscribe, state: state2, sql };
    });
  }
  function connected(x) {
    stream = x.stream;
    state2.pid = x.state.pid;
    state2.secret = x.state.secret;
  }
  async function init(sql2, slot2, publications) {
    if (!publications)
      throw new Error("Missing publication names");
    const xs = await sql2.unsafe(
      `CREATE_REPLICATION_SLOT ${slot2} TEMPORARY LOGICAL pgoutput NOEXPORT_SNAPSHOT`
    );
    const [x] = xs;
    const stream2 = await sql2.unsafe(
      `START_REPLICATION SLOT ${slot2} LOGICAL ${x.consistent_point} (proto_version '1', publication_names '${publications}')`
    ).writable();
    const state3 = {
      lsn: Buffer.concat(x.consistent_point.split("/").map((x2) => Buffer.from(("00000000" + x2).slice(-8), "hex")))
    };
    stream2.on("data", data);
    stream2.on("error", error);
    stream2.on("close", sql2.close);
    return { stream: stream2, state: xs.state };
    function error(e) {
      console.error("Unexpected error during logical streaming - reconnecting", e);
    }
    function data(x2) {
      if (x2[0] === 119) {
        parse(x2.subarray(25), state3, sql2.options.parsers, handle, options.transform);
      } else if (x2[0] === 107 && x2[17]) {
        state3.lsn = x2.subarray(1, 9);
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
      x2.fill(state3.lsn, 1);
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
function parse(x, state2, parsers2, handle, transform) {
  const char = (acc, [k, v]) => (acc[k.charCodeAt(0)] = v, acc);
  Object.entries({
    R: (x2) => {
      let i = 1;
      const r = state2[x2.readUInt32BE(i)] = {
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
      state2.date = Time(x2.readBigInt64BE(9));
      state2.lsn = x2.subarray(1, 9);
    },
    I: (x2) => {
      let i = 1;
      const relation = state2[x2.readUInt32BE(i)];
      const { row } = tuples(x2, relation.columns, i += 7, transform);
      handle(row, {
        command: "insert",
        relation
      });
    },
    D: (x2) => {
      let i = 1;
      const relation = state2[x2.readUInt32BE(i)];
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
      const relation = state2[x2.readUInt32BE(i)];
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
function largeObject(sql, oid, mode = 131072 | 262144) {
  return new Promise(async (resolve, reject) => {
    await sql.begin(async (sql2) => {
      let finish;
      !oid && ([{ oid }] = await sql2`select lo_creat(-1) as oid`);
      const [{ fd }] = await sql2`select lo_open(${oid}, ${mode}) as fd`;
      const lo = {
        writable,
        readable,
        close: () => sql2`select lo_close(${fd})`.then(finish),
        tell: () => sql2`select lo_tell64(${fd})`,
        read: (x) => sql2`select loread(${fd}, ${x}) as data`,
        write: (x) => sql2`select lowrite(${fd}, ${x})`,
        truncate: (x) => sql2`select lo_truncate64(${fd}, ${x})`,
        seek: (x, whence = 0) => sql2`select lo_lseek64(${fd}, ${x}, ${whence})`,
        size: () => sql2`
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
  const sql = Sql(handler2);
  Object.assign(sql, {
    get parameters() {
      return options.parameters;
    },
    largeObject: largeObject.bind(null, sql),
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
  return sql;
  function Sql(handler3) {
    handler3.debug = options.debug;
    Object.entries(options.types).reduce((acc, [name, type]) => {
      acc[name] = (x) => new Parameter(x, type.to);
      return acc;
    }, typed);
    Object.assign(sql2, {
      types: typed,
      typed,
      unsafe,
      notify,
      array,
      json: json3,
      file
    });
    return sql2;
    function typed(value, type) {
      return new Parameter(value, type);
    }
    function sql2(strings, ...args) {
      const query = strings && Array.isArray(strings.raw) ? new Query(strings, args, handler3, cancel) : typeof strings === "string" && !args.length ? new Identifier(options.transform.column.to ? options.transform.column.to(strings) : strings) : new Builder(strings, args);
      return query;
    }
    function unsafe(string, args = [], options2 = {}) {
      arguments.length === 2 && !Array.isArray(args) && (options2 = args, args = []);
      const query = new Query([string], args, handler3, cancel, {
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
          handler3(query2);
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
    const sql2 = listen.sql || (listen.sql = Postgres({
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
    channels[name] = { result: sql2`listen ${sql2.unsafe('"' + name.replace(/"/g, '""') + '"')}`, listeners: [listener] };
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
      return sql2`unlisten ${sql2.unsafe('"' + name.replace(/"/g, '""') + '"')}`;
    }
  }
  async function notify(channel, payload) {
    return await sql`select pg_notify(${channel}, ${"" + payload})`;
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
    const sql2 = Sql(handler3);
    sql2.release = () => {
      c.reserved = null;
      onopen(c);
    };
    return sql2;
    function handler3(q) {
      c.queue === full ? queue.push(q) : c.execute(q) || move(c, full);
    }
  }
  async function begin(options2, fn) {
    !fn && (fn = options2, options2 = "");
    const queries2 = queue_default();
    let savepoints = 0, connection2, prepare = null;
    try {
      await sql.unsafe("begin " + options2.replace(/[^a-z ]/ig, ""), [], { onexecute }).execute();
      return await Promise.race([
        scope(connection2, fn),
        new Promise((_, reject) => connection2.onclose = reject)
      ]);
    } catch (error) {
      throw error;
    }
    async function scope(c, fn2, name) {
      const sql2 = Sql(handler3);
      sql2.savepoint = savepoint;
      sql2.prepare = (x) => prepare = x.replace(/[^a-z0-9$-_. ]/gi);
      let uncaughtError, result;
      name && await sql2`savepoint ${sql2(name)}`;
      try {
        result = await new Promise((resolve, reject) => {
          const x = fn2(sql2);
          Promise.resolve(Array.isArray(x) ? Promise.all(x) : x).then(resolve, reject);
        });
        if (uncaughtError)
          throw uncaughtError;
      } catch (e) {
        await (name ? sql2`rollback to ${sql2(name)}` : sql2`rollback`);
        throw e instanceof PostgresError && e.code === "25P02" && uncaughtError || e;
      }
      if (!name) {
        prepare ? await sql2`prepare transaction '${sql2.unsafe(prepare)}'` : await sql2`commit`;
      }
      return result;
      function savepoint(name2, fn3) {
        if (name2 && Array.isArray(name2.raw))
          return savepoint((sql3) => sql3.apply(sql3, arguments));
        arguments.length === 1 && (fn3 = name2, name2 = null);
        return scope(c, fn3, "s" + savepoints++ + (name2 ? "_" + name2 : ""));
      }
      function handler3(q) {
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
  function json3(x) {
    return new Parameter(x, 3802);
  }
  function array(x, type) {
    if (!Array.isArray(x))
      return array(Array.from(arguments));
    return new Parameter(x, type || (x.length ? inferType(x) || 25 : 0), options.shared.typeArrayMap);
  }
  function handler2(query) {
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
  const env2 = process.env, o = (!a || typeof a === "string" ? b2 : a) || {}, { url: url2, multihost } = parseUrl(a), query = [...url2.searchParams].reduce((a2, [b3, c]) => (a2[b3] = c, a2), {}), host = o.hostname || o.host || multihost || url2.hostname || env2.PGHOST || "localhost", port = o.port || url2.port || env2.PGPORT || 5432, user = o.user || o.username || url2.username || env2.PGUSERNAME || env2.PGUSER || osUsername();
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
    database: o.database || o.db || (url2.pathname || "").slice(1) || env2.PGDATABASE || user,
    user,
    pass: o.pass || o.password || url2.password || env2.PGPASSWORD || "",
    ...Object.entries(defaults).reduce(
      (acc, [k, d]) => {
        const value = k in o ? o[k] : k in query ? query[k] === "disable" || query[k] === "false" ? false : query[k] : env2["PG" + k.toUpperCase()] || d;
        acc[k] = typeof value === "string" && ints.includes(k) ? +value : value;
        return acc;
      },
      {}
    ),
    connection: {
      application_name: env2.PGAPPNAME || "postgres.js",
      ...o.connection,
      ...Object.entries(query).reduce((acc, [k, v]) => (k in defaults || (acc[k] = v), acc), {})
    },
    types: o.types || {},
    target_session_attrs: tsa(o, url2, env2),
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
function tsa(o, url2, env2) {
  const x = o.target_session_attrs || url2.searchParams.get("target_session_attrs") || env2.PGTARGETSESSIONATTRS;
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
function parseUrl(url2) {
  if (!url2 || typeof url2 !== "string")
    return { url: { searchParams: /* @__PURE__ */ new Map() } };
  let host = url2;
  host = host.slice(host.indexOf("://") + 3).split(/[?/]/)[0];
  host = decodeURIComponent(host.slice(host.indexOf("@") + 1));
  const urlObj = new URL(url2.replace(host, host.split(",")[0]));
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

// supabase/functions/live/_neon_db.ts
var db = src_default(process.env.MRX_LIVE_DATABASE_URL || process.env.DATABASE_URL, { max: 3, prepare: false, connect_timeout: 8, idle_timeout: 20, transform: { undefined: null } });
var tables = /* @__PURE__ */ new Set(["cron_runs", "live_stats_sources", "live_stats_merged", "notifications", "matches_live", "live_predictions", "espn_feed_cache", "espn_match_map", "actu_foot_live_events", "live_scheduled_fixtures", "pronostics", "daily_predictions", "live_refresh_control"]);
var safe = (name) => {
  if (!/^[a-z_][a-z0-9_]*$/i.test(name)) throw Error("INVALID_COLUMN");
  return name;
};
var table = (name) => {
  if (!tables.has(name)) throw Error("INVALID_TABLE");
  return name;
};
var functions = /* @__PURE__ */ new Set(["espn_take_request_slot", "espn_provider_backoff", "upsert_live_fixture_status", "renew_live_refresh", "claim_live_refresh", "release_live_refresh", "odds_take_request_slot"]);
var Query2 = class {
  constructor(name) {
    this.name = name;
    table(name);
  }
  action = "select";
  columns = "*";
  data = null;
  conditions = [];
  sorts = [];
  maxRows = null;
  singleMode = false;
  returning = false;
  conflicts = [];
  orClause = null;
  select(columns = "*") {
    if (columns !== "*") columns.split(",").forEach((x) => safe(x.trim()));
    this.columns = columns;
    this.returning = true;
    return this;
  }
  insert(data) {
    this.action = "insert";
    this.data = data;
    return this;
  }
  upsert(data, options = {}) {
    this.action = "upsert";
    this.data = data;
    this.conflicts = String(options.onConflict || "").split(",").map((x) => x.trim()).filter(Boolean).map(safe);
    return this;
  }
  update(data) {
    this.action = "update";
    this.data = data;
    return this;
  }
  delete() {
    this.action = "delete";
    return this;
  }
  eq(key, val) {
    this.conditions.push({ text: safe(key) + " = ", value: val });
    return this;
  }
  gte(key, val) {
    this.conditions.push({ text: safe(key) + " >= ", value: val });
    return this;
  }
  lte(key, val) {
    this.conditions.push({ text: safe(key) + " <= ", value: val });
    return this;
  }
  lt(key, val) {
    this.conditions.push({ text: safe(key) + " < ", value: val });
    return this;
  }
  is(key, val) {
    if (val !== null) throw Error("UNSUPPORTED_IS");
    this.conditions.push({ text: safe(key) + " IS NULL", value: void 0 });
    return this;
  }
  in(key, vals) {
    if (!Array.isArray(vals) || vals.length === 0) {
      this.conditions.push({ text: "1=0", value: void 0 });
      return this;
    }
    this.conditions.push({ text: safe(key) + " IN ", value: vals });
    return this;
  }
  or(value) {
    if (value !== "telegram_sent.is.null,telegram_sent.eq.false") throw Error("UNSUPPORTED_OR");
    this.orClause = "(telegram_sent IS NULL OR telegram_sent = false)";
    return this;
  }
  order(key, opts = {}) {
    this.sorts.push({ key: safe(key), asc: opts.ascending !== false });
    return this;
  }
  limit(n) {
    this.maxRows = Math.max(0, Math.min(1e4, Math.floor(n)));
    return this;
  }
  single() {
    this.singleMode = true;
    return this;
  }
  maybeSingle() {
    this.singleMode = true;
    return this;
  }
  async execute() {
    const params = [];
    const bind = (v) => {
      params.push(v);
      return "$" + params.length;
    };
    let where = this.conditions.map((c) => c.value === void 0 ? c.text : Array.isArray(c.value) ? c.text + "(" + c.value.map(bind).join(",") + ")" : c.text + bind(c.value)).join(" AND ");
    if (this.orClause) where += (where ? " AND " : "") + this.orClause;
    let clause = where ? " WHERE " + where : "";
    const source = "public." + this.name;
    const order = this.sorts.length ? " ORDER BY " + this.sorts.map((s) => s.key + (s.asc ? " ASC" : " DESC")).join(",") : "";
    const limit = this.maxRows !== null ? " LIMIT " + this.maxRows : "";
    const cols = this.columns;
    let statement = "";
    if (this.action === "select") statement = "SELECT " + cols + " FROM " + source + clause + order + limit;
    else if (this.action === "delete") statement = "DELETE FROM " + source + clause + (this.returning ? " RETURNING " + cols : "");
    else if (this.action === "update") {
      const entries = Object.entries(this.data || {});
      if (!entries.length) throw Error("EMPTY_UPDATE");
      const assignments = entries.map(([key, v]) => safe(key) + "=" + bind(v)).join(",");
      statement = "UPDATE " + source + " SET " + assignments + clause + (this.returning ? " RETURNING " + cols : "");
    } else {
      const rows2 = Array.isArray(this.data) ? this.data : [this.data];
      if (!rows2.length) return { data: [], error: null };
      const keys = [...new Set(rows2.flatMap((x) => Object.keys(x || {})))].map(safe);
      statement = "INSERT INTO " + source + " (" + keys.join(",") + ") VALUES " + rows2.map((row) => "(" + keys.map((key) => bind(row?.[key] ?? null)).join(",") + ")").join(",");
      if (this.action === "upsert") {
        const conflict = this.conflicts.length ? this.conflicts.join(",") : "id";
        const updates = keys.filter((k) => !this.conflicts.includes(k)).map((k) => k + "=EXCLUDED." + k);
        statement += " ON CONFLICT (" + conflict + ") " + (updates.length ? "DO UPDATE SET " + updates.join(",") : "DO NOTHING");
      }
      if (this.returning) statement += " RETURNING " + cols;
    }
    const rows = await db.unsafe(statement, params);
    const data = this.returning || this.action === "select" ? this.singleMode ? rows[0] ?? null : Array.from(rows) : null;
    return { data, error: null };
  }
  then(resolve, reject) {
    return this.execute().catch((error) => ({ data: null, error: { code: error?.code || "PG_ERROR", message: error?.message || String(error) } })).then(resolve, reject);
  }
};
function createClient(_url, _key) {
  return { from: (name) => new Query2(name), rpc: async (name, args = {}) => {
    try {
      if (!functions.has(name)) throw Error("UNSUPPORTED_RPC");
      const paramNames = Object.keys(args).map(safe);
      const params = paramNames.map((k) => args[k]);
      const sql = "SELECT public." + name + "(" + params.map((_, i) => "$" + (i + 1)).join(",") + ") AS result";
      const rows = await db.unsafe(sql, params);
      return { data: rows[0]?.result, error: null };
    } catch (error) {
      return { data: null, error: { code: error?.code || "PG_ERROR", message: error?.message || String(error) } };
    }
  } };
}

// supabase/functions/_shared/telegram_rich.ts
function richBody(text2, rows, hasPhoto) {
  const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const image = hasPhoto ? '<img src="tg://photo?id=coupon"/>' : "";
  const lines = String(text2 || "").split(/\r?\n/).map((x) => x.trim());
  const groups = [];
  let current = [];
  for (const line of lines) {
    if (!line) {
      if (current.length) {
        groups.push(current);
        current = [];
      }
      continue;
    }
    current.push(line);
  }
  if (current.length) groups.push(current);
  const desc = groups.map((group, index) => {
    const value = group.map(escapeHtml).join("<br/>");
    return index === 0 && groups.length > 1 ? "<h3>" + value + "</h3>" : "<p>" + value + "</p>";
  }).join("");
  const buttons = rows.map((row) => {
    const nodes = row.filter((b2) => b2?.url && /^https?:\/\//.test(b2.url)).map((b2) => {
      const style = ["primary", "success", "danger"].includes(b2.style || "") ? b2.style : "primary";
      return '<tg-button type="url" style="' + style + '" url="' + escapeHtml(b2.url) + '">' + escapeHtml(b2.text) + "</tg-button>";
    });
    return nodes.length ? '<tg-button-row align="center">' + nodes.join("") + "</tg-button-row>" : "";
  }).filter(Boolean).join("\n");
  return image + desc + buttons;
}
function richPhotoPayload(text2, rows) {
  return {
    html: richBody(text2, rows, true),
    media: [{ id: "coupon", media: { type: "photo", media: "attach://coupon_photo" } }]
  };
}
async function richPhotoOrLegacy(botToken, chatId, bytes, caption, rows, legacy, filename = "coupon.png") {
  const rich = new FormData();
  rich.append("chat_id", chatId);
  rich.append("rich_message", JSON.stringify(richPhotoPayload(caption, rows)));
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  rich.append("coupon_photo", new Blob([copy.buffer], { type: "image/png" }), filename);
  const result = await fetch(
    "https://api.telegram.org/bot" + botToken + "/sendRichMessage",
    { method: "POST", body: rich }
  );
  if (result.status === 400 || result.status === 404) {
    console.warn("TELEGRAM_RICH_REJECTED", result.status, "legacy photo fallback");
    return fetch(
      "https://api.telegram.org/bot" + botToken + "/sendPhoto",
      { method: "POST", body: legacy }
    );
  }
  return result;
}

// supabase/functions/live/_neon_banner.ts
init_resvg_wasm();
var ART_BASE = "https://raw.githubusercontent.com/MrXPRONOS/MrXPRONOS_App/main/assets/images/";
var ART = {
  "1xbet_melbet": "telegram-xpvip-banner.png",
  "1win_betwinner": "telegram-xpvip-banner-1win-betwinner.png"
};
function liveBannerPack(date2 = /* @__PURE__ */ new Date()) {
  return Math.floor(date2.getTime() / 864e5) % 2 === 0 ? "1xbet_melbet" : "1win_betwinner";
}
var bannerCache = /* @__PURE__ */ new Map();
async function loadBanner(pack) {
  if (!ART[pack]) throw new Error("Unknown XPVIP banner pack: " + pack);
  let promise = bannerCache.get(pack);
  if (!promise) {
    promise = (async () => {
      const response = await fetch(ART_BASE + ART[pack]);
      if (!response.ok) throw new Error("XPVIP image HTTP " + response.status);
      return new Uint8Array(await response.arrayBuffer());
    })();
    bannerCache.set(pack, promise);
  }
  try {
    return await promise;
  } catch (e) {
    bannerCache.delete(pack);
    throw e;
  }
}
function dimensions(png) {
  if (png.length < 24 || png[0] !== 137 || png[1] !== 80 || png[2] !== 78 || png[3] !== 71) throw Error("Invalid PNG header");
  const view = new DataView(png.buffer, png.byteOffset, png.byteLength);
  const width = view.getUint32(16), height = view.getUint32(20);
  if (width < 1 || height < 1 || width > 8192 || height > 8192) throw Error("Invalid PNG size");
  return { width, height };
}
async function attachLiveSponsorBanner(couponPng) {
  try {
    const pack = liveBannerPack();
    const [coupon, banner] = await Promise.all([Promise.resolve(couponPng), loadBanner(pack)]);
    const cd = dimensions(coupon), bd = dimensions(banner);
    const height = Math.max(1, Math.round(bd.height * cd.width / bd.width));
    if (height > cd.width / 3) throw new Error("XPVIP banner aspect ratio invalid");
    const bannerB64 = Buffer.from(banner).toString("base64");
    const couponB64 = Buffer.from(coupon).toString("base64");
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + cd.width + '" height="' + (height + cd.height) + '" viewBox="0 0 ' + cd.width + " " + (height + cd.height) + '"><image href="data:image/png;base64,' + bannerB64 + '" x="0" y="0" width="' + cd.width + '" height="' + height + '" preserveAspectRatio="none"/><image href="data:image/png;base64,' + couponB64 + '" x="0" y="' + height + '" width="' + cd.width + '" height="' + cd.height + '"/></svg>';
    const png = new Resvg2(svg, { fitTo: { mode: "original" } }).render().asPng();
    if (png.byteLength < 1500) throw Error("Composited PNG invalid");
    return png;
  } catch (error) {
    console.warn("LIVE_BANNER_FALLBACK", String(error));
    return couponPng;
  }
}

// supabase/functions/_shared/live_odds_failover.ts
var PROVIDERS = ["MOVIODDS", "PINNWIRE", "ODDSLINK", "GOALDIR", "ODDSHARVESTER"];
var usage = /* @__PURE__ */ new Map();
var normalize = (v) => String(v ?? "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]/gi, "").toLowerCase();
function number(v) {
  if (v === null || v === void 0 || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
var date = (v) => typeof v === "string" ? Date.parse(v) : NaN;
function status(provider, dailyCap) {
  const day = (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
  const old = usage.get(provider);
  const state2 = old?.day === day ? old : { day, count: 0, disabledUntil: 0 };
  usage.set(provider, state2);
  return state2.count < dailyCap && Date.now() >= state2.disabledUntil ? state2 : null;
}
async function fetchFiveSourceLiveOdds(input) {
  if (!Number.isFinite(input.line) || input.line <= 0 || !input.match_id || !input.market) return null;
  for (const provider of PROVIDERS) {
    const base = Deno.env.get("LIVE_ODDS_" + provider + "_URL")?.trim();
    if (!base || !base.startsWith("https://")) continue;
    const capRaw = Number(Deno.env.get("LIVE_ODDS_" + provider + "_DAILY_LIMIT") || "");
    const cap2 = Number.isFinite(capRaw) && capRaw > 0 ? Math.floor(capRaw) : provider === "PINNWIRE" ? 90 : provider === "ODDSLINK" ? 30 : provider === "GOALDIR" ? 100 : provider === "MOVIODDS" ? 250 : 20;
    const state2 = status(provider, cap2);
    if (!state2) continue;
    try {
      const u = new URL(base);
      for (const [key, value] of Object.entries({
        match_id: input.match_id,
        home: input.home,
        away: input.away,
        kickoff: input.kickoff || "",
        market: input.market,
        line: String(input.line),
        minute: String(input.minute),
        phase: "live"
      }))
        u.searchParams.set(key, value);
      const token = Deno.env.get("LIVE_ODDS_" + provider + "_TOKEN") || "";
      const headers = { "Accept": "application/json" };
      if (token) headers["Authorization"] = "Bearer " + token;
      const ctl = new AbortController();
      const id = setTimeout(() => ctl.abort(), 4500);
      let response;
      try {
        response = await fetch(u, { headers, signal: ctl.signal });
      } finally {
        clearTimeout(id);
      }
      state2.count++;
      if ([401, 402, 403, 429].includes(response.status)) {
        state2.disabledUntil = response.status === 429 ? Date.now() + 36e5 : Date.now() + 864e5;
        console.warn("LIVE_ODDS_PROVIDER_RESTRICTED", provider, response.status);
        continue;
      }
      if (!response.ok) continue;
      const payload = await response.json().catch(() => null);
      const body = payload?.data ?? payload;
      if (!body || Array.isArray(body) || typeof body !== "object") continue;
      const sourceMatch = String(body.match_id ?? body.event_id ?? "");
      const identityOk = sourceMatch === input.match_id || normalize(body.home_team ?? body.home) === normalize(input.home) && normalize(body.away_team ?? body.away) === normalize(input.away) && input.home.length > 0 && input.away.length > 0 && Number.isFinite(date(body.kickoff)) && Number.isFinite(date(input.kickoff)) && Math.abs(date(body.kickoff) - date(input.kickoff)) < 72e5;
      const market = normalize(body.market ?? body.market_type);
      const requested = normalize(input.market);
      const line = number(body.line ?? body.threshold ?? body.point);
      const price = number(body.odds ?? body.price ?? body.decimal_odds);
      const seen = date(body.updated_at ?? body.captured_at ?? body.timestamp);
      const age = Date.now() - seen;
      const phase = String(body.phase ?? "").toLowerCase();
      if (!identityOk || !market || market !== requested || line === null || Math.abs(line - input.line) > 0.01 || price === null || price <= 1.01 || price > 100 || !Number.isFinite(seen) || age < -3e4 || age > 12e4 || !["live", "inplay", "in-play"].includes(phase)) continue;
      return { odds: Number(price.toFixed(3)), source: provider.toLowerCase(), line };
    } catch (e) {
      console.warn("LIVE_ODDS_PROVIDER_FAILED", provider, String(e).slice(0, 130));
      continue;
    }
  }
  return null;
}

// supabase/functions/_shared/live_bookmaker_direct.ts
var clean = (x) => String(x ?? "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");
var number2 = (x) => x == null || x === "" ? NaN : Number(x);
var time = (x) => typeof x === "string" ? Date.parse(x) : NaN;
var cap = (n, fallback) => {
  const x = Number(Deno.env.get(n));
  return Number.isFinite(x) && x > 0 ? Math.floor(x) : fallback;
};
var cache = /* @__PURE__ */ new Map();
var disabled = /* @__PURE__ */ new Map();
function marketMatches(label, input) {
  const name = clean(label);
  const wanted = clean(input.market);
  if (wanted === "totalcorners") return name.includes("corner") && !name.includes("firsthalf") && !name.includes("1sthalf");
  if (wanted === "totalshots") return name.includes("totalshots") && !name.includes("ontarget") && !name.includes("player") && !name.includes("firsthalf");
  if (wanted === "totalfouls") return name.includes("fouls") && !name.includes("firsthalf");
  return false;
}
function fixtureMatches(v, input) {
  const home = clean(v?.home ?? v?.home_team ?? v?.homeTeam?.name);
  const away = clean(v?.away ?? v?.away_team ?? v?.awayTeam?.name);
  if (!home || !away || !clean(input.home) || !clean(input.away) || home !== clean(input.home) || away !== clean(input.away)) return false;
  const got = time(v?.kickoff_utc ?? v?.kickoff ?? v?.starts ?? v?.commence_time ?? v?.start_time);
  const wanted = time(input.kickoff);
  return Number.isFinite(got) && Number.isFinite(wanted) && Math.abs(got - wanted) <= 72e5;
}
function isFresh(v, maxAge = 12e4) {
  const t = time(v?.updated_at ?? v?.timestamp ?? v?.polled_at ?? v?.last_update);
  return Number.isFinite(t) && Date.now() - t >= -3e4 && Date.now() - t <= maxAge;
}
function extractMovi(data, input) {
  const events = Array.isArray(data?.matches) ? data.matches : Array.isArray(data) ? data : [];
  const match = events.find((x) => x?.in_play === true && fixtureMatches(x, input));
  if (!match) return null;
  for (const q of match.quotes ?? []) {
    if (q?.suspended !== false && q?.suspended !== void 0) continue;
    if (!marketMatches(q?.group_name ?? q?.market, input)) continue;
    const selection = clean(q?.side ?? q?.label);
    if (!["over", "o"].includes(selection) && !selection.startsWith("over")) continue;
    const labelLine = String(q?.label ?? "").match(/over\s*(\d+(?:\.\d+)?)/i);
    const line = number2(q?.line ?? q?.point ?? labelLine?.[1]);
    const price = number2(q?.odds_dec ?? q?.price);
    if (!Number.isFinite(line) || Math.abs(line - input.line) > 0.01 || !Number.isFinite(price) || price <= 1.01 || price > 100) continue;
    if (!isFresh({ updated_at: match?.polled_at })) continue;
    return { odds: Number(price.toFixed(3)), line, source: "moviodds" };
  }
  return null;
}
function extractPinnwire(data, input) {
  const events = Array.isArray(data?.events) ? data.events : Array.isArray(data) ? data : [];
  const match = events.find((x) => fixtureMatches(x, input) && x?.live === true);
  if (!match || !isFresh(match)) return null;
  const markets = Array.isArray(match.markets) ? match.markets : [];
  for (const m of markets) {
    if (!marketMatches(m?.name ?? m?.market, input)) continue;
    if (m?.suspended === true) continue;
    const line = number2(m?.line ?? m?.points);
    const price = number2(m?.over ?? m?.odds?.over);
    if (Number.isFinite(line) && Math.abs(line - input.line) <= 0.01 && Number.isFinite(price) && price > 1.01 && price <= 100)
      return { odds: Number(price.toFixed(3)), line, source: "pinnwire" };
  }
  return null;
}
async function getJSON(provider, input, db2) {
  const url2 = provider === "moviodds" ? "https://moviodds.com/odds?sport=soccer&in_play=1&stats=1" : Deno.env.get("LIVE_ODDS_PINNWIRE_DIRECT_URL") || "";
  if (!url2 || !url2.startsWith("https://")) return null;
  const key = provider + ":" + url2;
  const stored = cache.get(key);
  if (stored && Date.now() - stored.at < 15e3) return stored.data;
  if ((disabled.get(provider) || 0) > Date.now()) return null;
  const limits = provider === "moviodds" ? { day: cap("LIVE_MOVIODDS_DAILY_CAP", 1800), minute: cap("LIVE_MOVIODDS_MINUTE_CAP", 3) } : { day: cap("LIVE_PINNWIRE_DAILY_CAP", 90), minute: cap("LIVE_PINNWIRE_MINUTE_CAP", 2) };
  if (provider === "pinnwire" && !Deno.env.get("LIVE_ODDS_PINNWIRE_KEY")) return null;
  const slot = await db2.rpc("odds_take_request_slot", {
    p_provider: provider,
    p_day_limit: limits.day,
    p_minute_limit: limits.minute
  });
  if (slot.error || slot.data !== true) {
    console.warn("ODDS_QUOTA_BLOCK", provider);
    return null;
  }
  const ac = new AbortController();
  const timer2 = setTimeout(() => ac.abort(), 5e3);
  try {
    const headers = { Accept: "application/json" };
    if (provider === "moviodds") {
      const apiKey = Deno.env.get("MOVIODDS_API_KEY");
      if (apiKey) headers["X-API-Key"] = apiKey;
    }
    if (provider === "pinnwire") {
      const secret = Deno.env.get("LIVE_ODDS_PINNWIRE_KEY");
      if (!secret) return null;
      headers["x-api-key"] = secret;
    }
    const res = await fetch(url2, { headers, signal: ac.signal });
    if ([401, 402, 403, 429].includes(res.status)) {
      disabled.set(provider, Date.now() + 36e5);
      return null;
    }
    if (!res.ok) return null;
    const body = await res.json();
    cache.set(key, { at: Date.now(), data: body });
    return body;
  } catch (e) {
    console.warn("LIVE_ODDS_UPSTREAM_UNAVAILABLE", provider, e instanceof Error ? e.name : "error");
    return null;
  } finally {
    clearTimeout(timer2);
  }
}
async function fetchLiveBookmakerOdds(input, db2) {
  if (!input.match_id || !input.market || !Number.isFinite(input.line) || input.line <= 0) return null;
  for (const p of ["moviodds", "pinnwire"]) {
    const raw = await getJSON(p, input, db2);
    if (!raw) continue;
    const q = p === "moviodds" ? extractMovi(raw, input) : extractPinnwire(raw, input);
    if (q) return q;
  }
  return null;
}
function verifiedStatNumber(x, field) {
  if (x === null || x === void 0 || x === "" || typeof x === "boolean") return null;
  const n = typeof x === "number" ? x : Number(x);
  const max = field === "ball_possession" ? 100 : 400;
  return Number.isFinite(n) && n >= 0 && n <= max ? n : null;
}
function observedSoccerPairs(value) {
  if (!value || typeof value !== "object") return null;
  if (value.sport && !["soccer", "football"].includes(String(value.sport).toLowerCase())) return null;
  const home = value.home, away = value.away;
  if (!home || typeof home !== "object" || !away || typeof away !== "object") return null;
  const specs = {
    corner_kicks: ["corners", "corner_kicks"],
    total_shots: ["shots", "total_shots", "shots_total"],
    shots_on_target: ["shots_on_target"],
    shots_off_target: ["shots_off_target"],
    attacks: ["attacks"],
    dangerous_attacks: ["dangerous_attacks"],
    yellow_cards: ["yellow_cards"],
    red_cards: ["red_cards"],
    ball_possession: ["possession", "ball_possession"]
  };
  const result = { home: {}, away: {} };
  for (const [target, keys] of Object.entries(specs)) {
    const pick = (side) => {
      for (const k of keys) {
        const n = verifiedStatNumber(side[k], target);
        if (n !== null) return n;
      }
      return null;
    };
    const h = pick(home), a = pick(away);
    if (h !== null && a !== null) {
      result.home[target] = h;
      result.away[target] = a;
    }
  }
  return Object.keys(result.home).length ? result : null;
}
async function fetchVerifiedMoviOddsLiveStats(inputs, db2) {
  if (!inputs.length) return [];
  const board = await getJSON("moviodds", {
    match_id: "audit",
    home: "",
    away: "",
    market: "",
    line: 0,
    minute: 0
  }, db2);
  if (!board) return [];
  const events = Array.isArray(board?.matches) ? board.matches : [];
  const used = /* @__PURE__ */ new Set();
  const results = [];
  for (const input of inputs.slice(0, 100)) {
    if (!input.match_id || used.has(input.match_id)) continue;
    const row = events.find((event) => event?.in_play === true && fixtureMatches(event, { ...input, market: "", line: 0, minute: 0 }));
    if (!row || !isFresh({ updated_at: row.polled_at }, 18e4) || !isFresh({ updated_at: row.stats?.updated_at }, 18e4)) continue;
    const stats = observedSoccerPairs(row.stats);
    if (!stats) continue;
    if (row.id === null || row.id === void 0 || String(row.id).trim() === "") continue;
    results.push({ match_id: input.match_id, provider_id: String(row.id), stats });
    used.add(input.match_id);
  }
  return results;
}

// supabase/functions/live/index.neon.ts
var BSD_API_TOKEN = Deno.env.get("BSD_API_TOKEN") || "";
var SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
var SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
var DEFAULT_TZ = Deno.env.get("BSD_TZ") || "Europe/Paris";
var CRON_SECRET = Deno.env.get("CRON_SECRET") || "";
var DEBUG_KEY = Deno.env.get("DEBUG_KEY") || "";
var LIVE_PROP_ODDS_URL = Deno.env.get("LIVE_PROP_ODDS_URL") || "";
var LIVE_PROP_ODDS_TOKEN = Deno.env.get("LIVE_PROP_ODDS_TOKEN") || "";
var LIVE_REQUIRE_BOOKMAKER_LINE = (Deno.env.get("LIVE_REQUIRE_BOOKMAKER_LINE") || "0") === "1";
var TELEGRAM_BOT_TOKEN = Deno.env.get("TELEGRAM_BOT_TOKEN") || "";
var TELEGRAM_CHAT_ID = Deno.env.get("TELEGRAM_CHAT_ID") || "";
var TELEGRAM_CHAT_ID_SECONDARY = Deno.env.get("TELEGRAM_CHAT_ID_SECONDARY") || "@mrxpronosfr";
var SITE_URL = Deno.env.get("SITE_URL") || "https://mrxpronos.github.io/MrXPRONOS_App/";
var TELEGRAM_IN_REFRESH = true;
var BSD_API_BASE = "https://sports.bzzoiro.com/api/v2";
var BSD_COVERAGE_URL = "https://sports.bzzoiro.com/api/v2/coverage/?sport=football";
var BSD_IMG_BASE = "https://sports.bzzoiro.com/img";
var ENABLE_ESPN_MERGE = String(Deno.env.get("ENABLE_ESPN_MERGE") || "true").toLowerCase() !== "false";
var LIVE_REFRESH_BATCH_SIZE = Math.max(
  1,
  Math.min(5, safeEnvInt("LIVE_REFRESH_BATCH_SIZE", 5))
);
var LIVE_REFRESH_MAX_BATCHES = Math.max(
  1,
  Math.min(50, safeEnvInt("LIVE_REFRESH_MAX_BATCHES", 20))
);
var BSD_STATS_MAX_CALLS_PER_REFRESH = Math.max(
  1,
  Math.min(5, safeEnvInt("BSD_STATS_MAX_CALLS_PER_REFRESH", 2))
);
var BSD_STATS_REFRESH_SECONDS = Math.max(
  45,
  Math.min(600, safeEnvInt("BSD_STATS_REFRESH_SECONDS", 120))
);
var SPORTSCORE_STATS_REFRESH_SECONDS = Math.max(
  120,
  Math.min(1200, safeEnvInt("SPORTSCORE_STATS_REFRESH_SECONDS", 300))
);
var BSD_STATS_QUOTA_RESERVE = Math.max(
  250,
  Math.min(3e3, safeEnvInt("BSD_STATS_QUOTA_RESERVE", 900))
);
var T_STATS_SOURCES = "live_stats_sources";
var T_STATS_MERGED = "live_stats_merged";
var DAILY_DEFAULT_STAKE = 5e5;
if (!BSD_API_TOKEN) console.error("BSD_API_TOKEN non d\xE9fini");
if (!SUPABASE_URL) console.error("SUPABASE_URL non d\xE9fini");
if (!SUPABASE_SERVICE_ROLE_KEY) console.error("SUPABASE_SERVICE_ROLE_KEY non d\xE9fini");
var supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
async function setCronRun(jobName, success, details = {}) {
  const at = nowIso();
  console.log("CRON_RUN", {
    job_name: jobName,
    success,
    details,
    at
  });
  try {
    const { error } = await supabase.from("cron_runs").upsert({
      name: jobName,
      last_run_at: at,
      last_ok: success,
      meta: details
    }, { onConflict: "name" });
    if (error) console.warn("CRON_HEALTH_PERSIST_FAILED", jobName, error.message);
  } catch (e) {
    console.warn("CRON_HEALTH_PERSIST_FAILED", jobName, e?.message || String(e));
  }
}
var corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, x-cron-secret"
};
function json2(data, status2 = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status: status2,
    headers: { ...corsHeaders, ...headers, "Content-Type": "application/json" }
  });
}
function safeNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}
function safeEnvInt(name, fallback) {
  const n = Number(Deno.env.get(name) || "");
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}
function computeFreshness(updatedAt) {
  if (!updatedAt) return null;
  const ts = typeof updatedAt === "number" ? updatedAt : new Date(updatedAt).getTime();
  if (!Number.isFinite(ts)) return null;
  return Math.max(0, Math.floor((Date.now() - ts) / 1e3));
}
function nowIso() {
  return (/* @__PURE__ */ new Date()).toISOString();
}
function todayYYYYMMDD() {
  return (/* @__PURE__ */ new Date()).toISOString().slice(0, 10).replace(/-/g, "");
}
function toDateKey(value) {
  const raw = String(value ?? "").trim();
  if (/^\d{8}$/.test(raw)) return raw;
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10).replace(/-/g, "");
  const d = raw ? new Date(raw) : /* @__PURE__ */ new Date();
  if (Number.isFinite(d.getTime())) return d.toISOString().slice(0, 10).replace(/-/g, "");
  return todayYYYYMMDD();
}
function stripAccents(value) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}
function normalizeTeamKey(name) {
  return stripAccents(String(name ?? "")).toLowerCase().replace(/&/g, " and ").replace(/\b(fc|cf|sc|afc|club|de|da|do|the|football|soccer)\b/g, " ").replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}
function slugTeam(name) {
  return normalizeTeamKey(name).replace(/\s+/g, "-") || "unknown";
}
function getMatchEventDate(match) {
  return match?.event_date ?? match?.date ?? match?.start_time ?? match?.startTime ?? match?.kickoff ?? match?.raw_data?.event_date ?? match?.raw_data?.date ?? null;
}
function getLeagueName(match) {
  return match?.league_name ?? match?.league?.name ?? match?.competition?.name ?? match?.competitionDisplayName ?? match?.raw_data?.league?.name ?? match?.raw_data?.competition?.name ?? "Football";
}
function buildCanonicalMatchId(match) {
  const dateKey = toDateKey(getMatchEventDate(match));
  const home = slugTeam(match?.home_team ?? match?.homeTeam ?? match?.home?.name);
  const away = slugTeam(match?.away_team ?? match?.awayTeam ?? match?.away?.name);
  return `${dateKey}_${home}_${away}`;
}
function tokenSet(value) {
  const clean2 = normalizeTeamKey(value);
  if (!clean2) return /* @__PURE__ */ new Set();
  return new Set(clean2.split(" ").filter(Boolean));
}
function jaccardSimilarity(a, b2) {
  const A = tokenSet(a);
  const B = tokenSet(b2);
  if (!A.size || !B.size) return 0;
  let intersection = 0;
  for (const x of A) {
    if (B.has(x)) intersection++;
  }
  const union = (/* @__PURE__ */ new Set([...A, ...B])).size;
  return union ? intersection / union : 0;
}
function sameMatchScore(a, b2) {
  if (toDateKey(getMatchEventDate(a)) !== toDateKey(getMatchEventDate(b2))) return 0;
  const sameOrder = (jaccardSimilarity(a?.home_team, b2?.home_team) + jaccardSimilarity(a?.away_team, b2?.away_team)) / 2;
  const leagueA = normalizeTeamKey(a?.league_name || a?.league?.name || "");
  const leagueB = normalizeTeamKey(b2?.league_name || b2?.league?.name || "");
  if (leagueA && leagueB && leagueA !== leagueB && jaccardSimilarity(leagueA, leagueB) < 0.5) return 0;
  const dateA = Date.parse(getMatchEventDate(a));
  const dateB = Date.parse(getMatchEventDate(b2));
  if (Number.isFinite(dateA) && Number.isFinite(dateB) && Math.abs(dateA - dateB) > 4 * 36e5) return 0;
  return sameOrder;
}
function getHomeStats(stats) {
  return stats?.home || {};
}
function getAwayStats(stats) {
  return stats?.away || {};
}
function nullableNumber(value) {
  return parseEspnNumber(value);
}
function hasCompleteStatPair(stats, key) {
  return nullableNumber(stats?.home?.[key]) != null && nullableNumber(stats?.away?.[key]) != null;
}
function statPairTotal(stats, key, totalKey) {
  const totals = stats?.totals || {};
  const tk = totalKey || key;
  const explicit = nullableNumber(totals?.[tk]);
  if (explicit != null) return explicit;
  const home = nullableNumber(getHomeStats(stats)?.[key]);
  const away = nullableNumber(getAwayStats(stats)?.[key]);
  if (home == null || away == null) return NaN;
  return home + away;
}
function statsCompleteness(stats) {
  const shots = hasCompleteStatPair(stats, "total_shots");
  const shotsOnTarget = hasCompleteStatPair(stats, "shots_on_target");
  const corners = hasCompleteStatPair(stats, "corner_kicks");
  const fouls = hasCompleteStatPair(stats, "fouls");
  const core = [shots, corners, fouls].filter(Boolean).length;
  return {
    shots,
    shots_on_target: shotsOnTarget,
    corners,
    fouls,
    core_complete: core,
    score: Math.round(core / 3 * 100)
  };
}
function ensureLiveStatsShape(stats) {
  const home = { ...stats?.home || {} };
  const away = { ...stats?.away || {} };
  const totals = { ...stats?.totals || {} };
  const pairs = [
    ["corner_kicks", "corners"],
    ["fouls", "fouls"],
    ["yellow_cards", "yellow_cards"],
    ["red_cards", "red_cards"],
    ["total_shots", "total_shots"],
    ["shots_on_target", "shots_on_target"],
    // Additional observed SportScore statistics. These enrich the feed but
    // do not become substitute corners/fouls/total-shots predictions.
    ["shots_off_target", "shots_off_target"],
    ["attacks", "attacks"],
    ["dangerous_attacks", "dangerous_attacks"]
  ];
  for (const [key, totalKey] of pairs) {
    home[key] = nullableNumber(home[key]);
    away[key] = nullableNumber(away[key]);
    const explicit = nullableNumber(totals[totalKey]);
    if (explicit != null) {
      totals[totalKey] = explicit;
    } else if (home[key] != null && away[key] != null) {
      totals[totalKey] = home[key] + away[key];
    } else {
      totals[totalKey] = null;
    }
  }
  if (home.ball_possession !== void 0) {
    home.ball_possession = nullableNumber(home.ball_possession);
  }
  if (away.ball_possession !== void 0) {
    away.ball_possession = nullableNumber(away.ball_possession);
  }
  return { ...stats, home, away, totals };
}
function applyStatPairIfBetter(base, extra, key, totalKey, preferFreshSource = false) {
  const tk = totalKey || key;
  const bh = nullableNumber(base?.home?.[key]);
  const ba = nullableNumber(base?.away?.[key]);
  const eh = nullableNumber(extra?.home?.[key]);
  const ea = nullableNumber(extra?.away?.[key]);
  const baseComplete = bh != null && ba != null;
  const extraComplete = eh != null && ea != null;
  if (extraComplete) {
    const baseTotal = baseComplete ? bh + ba : -1;
    const extraTotal = eh + ea;
    if (!baseComplete || preferFreshSource || extraTotal >= baseTotal) {
      base.home[key] = eh;
      base.away[key] = ea;
      base.totals[tk] = extraTotal;
    }
    return;
  }
  if (bh == null && eh != null) base.home[key] = eh;
  if (ba == null && ea != null) base.away[key] = ea;
  const nh = nullableNumber(base?.home?.[key]);
  const na = nullableNumber(base?.away?.[key]);
  base.totals[tk] = nh != null && na != null ? nh + na : null;
}
function mergeLiveStats(primaryStats, secondaryStats, preferFreshSource = false) {
  const merged = ensureLiveStatsShape(primaryStats || {});
  const extra = ensureLiveStatsShape(secondaryStats || {});
  applyStatPairIfBetter(merged, extra, "corner_kicks", "corners", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "fouls", "fouls", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "yellow_cards", "yellow_cards", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "red_cards", "red_cards", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "total_shots", "total_shots", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "shots_on_target", "shots_on_target", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "shots_off_target", "shots_off_target", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "attacks", "attacks", preferFreshSource);
  applyStatPairIfBetter(merged, extra, "dangerous_attacks", "dangerous_attacks", preferFreshSource);
  const hp = nullableNumber(extra?.home?.ball_possession);
  const ap = nullableNumber(extra?.away?.ball_possession);
  if (hp != null) merged.home.ball_possession = hp;
  if (ap != null) merged.away.ball_possession = ap;
  return ensureLiveStatsShape(merged);
}
function getMatchLiveStats(match) {
  return match?.live_stats || match?.raw_data?.live_stats || {};
}
function getSourceMatchId(match, sourceName) {
  if (sourceName === "espn") {
    return String(match?.source_match_id || match?.espn_id || match?.id || "");
  }
  return String(match?.id || match?.source_match_id || "");
}
function sourceRowFromMatch(match, sourceName) {
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(match));
  const canonical = buildCanonicalMatchId(match);
  return {
    canonical_match_id: canonical,
    source_name: sourceName,
    source_match_id: getSourceMatchId(match, sourceName),
    home_team: match?.home_team ?? null,
    away_team: match?.away_team ?? null,
    league_name: getLeagueName(match),
    event_date: getMatchEventDate(match) ? new Date(getMatchEventDate(match)).toISOString() : null,
    minute: safeNumber(match?.current_minute ?? match?.minute, 0),
    home_score: safeNumber(match?.home_score, 0),
    away_score: safeNumber(match?.away_score, 0),
    is_live: Boolean(match?.is_live ?? true),
    is_finished: Boolean(match?.is_finished ?? false),
    stats_json: liveStats,
    raw_json: match,
    updated_at: nowIso()
  };
}
function mergedRowFromMatch(match) {
  const canonical = buildCanonicalMatchId(match);
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(match));
  const raw = match?.raw_data || {};
  return {
    canonical_match_id: canonical,
    primary_match_id: String(match?.id),
    home_team: match?.home_team ?? null,
    away_team: match?.away_team ?? null,
    league_name: getLeagueName(match),
    event_date: getMatchEventDate(match) ? new Date(getMatchEventDate(match)).toISOString() : null,
    minute: safeNumber(match?.current_minute ?? match?.minute, 0),
    home_score: safeNumber(match?.home_score, 0),
    away_score: safeNumber(match?.away_score, 0),
    is_live: Boolean(match?.is_live ?? true),
    is_finished: Boolean(match?.is_finished ?? false),
    merged_stats: liveStats,
    sources_used: raw?.merge_meta?.sources || [],
    confidence_score: safeNumber(raw?.merge_meta?.confidence_score, 0),
    merged_match_json: match,
    updated_at: nowIso()
  };
}
function sourceStatsRowScore(row) {
  const core = statsCompleteness(row?.stats_json || {}).core_complete;
  return core * 100 + Math.min(110, safeNumber(row?.minute, 0)) + (row?.is_live ? 3 : 0);
}
function mergedStatsRowScore(row) {
  const core = statsCompleteness(row?.merged_stats || {}).core_complete;
  return core * 100 + Math.min(110, safeNumber(row?.minute, 0)) + (row?.is_live ? 3 : 0);
}
function uniqueSourceStatsRows(rows) {
  const byKey = /* @__PURE__ */ new Map();
  for (const row of rows) {
    if (!row?.source_name || !row?.source_match_id) continue;
    const key = String(row.source_name) + "\\0" + String(row.source_match_id);
    const prior = byKey.get(key);
    if (!prior || sourceStatsRowScore(row) > sourceStatsRowScore(prior)) byKey.set(key, row);
  }
  return [...byKey.values()];
}
function uniqueMergedStatsRows(rows) {
  const byKey = /* @__PURE__ */ new Map();
  for (const row of rows) {
    if (!row?.canonical_match_id) continue;
    const key = String(row.canonical_match_id);
    const prior = byKey.get(key);
    if (!prior) {
      byKey.set(key, row);
      continue;
    }
    const rowIsEspn = Boolean(row?.merged_match_json?.raw_data?.espn_primary_stats);
    const priorIsEspn = Boolean(prior?.merged_match_json?.raw_data?.espn_primary_stats);
    const winner = priorIsEspn !== rowIsEspn ? priorIsEspn ? prior : row : mergedStatsRowScore(row) > mergedStatsRowScore(prior) ? row : prior;
    const other = winner === row ? prior : row;
    const sources = [.../* @__PURE__ */ new Set([...winner.sources_used || [], ...other.sources_used || []])];
    const winnerMatch = winner.merged_match_json || {};
    const winnerRaw = winnerMatch.raw_data || {};
    const otherRaw = other.merged_match_json?.raw_data || {};
    const bsdPrimary = winnerRaw.bsd_primary_stats || otherRaw.bsd_primary_stats;
    const espnPrimary = winnerRaw.espn_primary_stats || otherRaw.espn_primary_stats;
    const joined = mergeLiveStats(winner.merged_stats, other.merged_stats);
    const withBsd = bsdPrimary ? preserveBsdCoreMarketPairs(bsdPrimary, joined) : joined;
    const stats = ensureLiveStatsShape(espnPrimary ? preferObservedCoreMarketPairs(espnPrimary, withBsd) : withBsd);
    const preferredMinute = safeNumber(winner.minute, 0);
    const updatedMatch = {
      ...winnerMatch,
      current_minute: Math.max(preferredMinute, safeNumber(other.minute, 0)),
      live_stats: stats,
      raw_data: {
        ...winnerRaw,
        live_stats: stats,
        bsd_primary_stats: bsdPrimary || void 0,
        espn_primary_stats: espnPrimary || void 0,
        provider_refs: { ...otherRaw.provider_refs || {}, ...winnerRaw.provider_refs || {} },
        merge_meta: { ...winnerRaw.merge_meta || {}, sources }
      }
    };
    byKey.set(key, {
      ...winner,
      minute: updatedMatch.current_minute,
      is_live: Boolean(winner.is_live || other.is_live),
      merged_stats: stats,
      sources_used: sources,
      confidence_score: Math.max(safeNumber(winner.confidence_score, 0), safeNumber(other.confidence_score, 0)),
      merged_match_json: updatedMatch
    });
  }
  return [...byKey.values()];
}
async function persistStatsSourcesAndMerged(sourceRows, mergedMatches) {
  const uniqueSources = uniqueSourceStatsRows(sourceRows);
  const mergedRows = uniqueMergedStatsRows(mergedMatches.map(mergedRowFromMatch));
  if (uniqueSources.length !== sourceRows.length || mergedRows.length !== mergedMatches.length) {
    console.info("LIVE_PROVIDER_DEDUP", {
      source_rows: sourceRows.length,
      unique_source_rows: uniqueSources.length,
      merged_rows: mergedMatches.length,
      unique_merged_rows: mergedRows.length
    });
  }
  if (uniqueSources.length) {
    const { error } = await supabase.from(T_STATS_SOURCES).upsert(uniqueSources, { onConflict: "source_name,source_match_id" });
    if (error) console.error("Agr\xE9gation sources non persist\xE9e:", error);
  }
  if (mergedRows.length) {
    const { error } = await supabase.from(T_STATS_MERGED).upsert(mergedRows, { onConflict: "canonical_match_id" });
    if (error) console.error("Agr\xE9gation stats non persist\xE9e:", error);
  }
}
function extractPath(url2, fnName = "live") {
  const p = url2.pathname;
  const needle = `/${fnName}`;
  const i = p.lastIndexOf(needle);
  if (i >= 0) {
    const rest = p.slice(i + needle.length);
    return rest === "" ? "/" : rest;
  }
  return p || "/";
}
function requireCronAuth(req, url2) {
  if (!CRON_SECRET) throw new Error("CRON_SECRET not configured");
  const auth = req.headers.get("authorization") || "";
  const x = req.headers.get("x-cron-secret") || "";
  const q = url2.searchParams.get("key") || "";
  const bearerOk = auth.toLowerCase().startsWith("bearer ") && auth.slice(7).trim() === CRON_SECRET;
  const ok = bearerOk || x === CRON_SECRET || q === CRON_SECRET;
  if (!ok) throw new Error("Unauthorized (CRON_SECRET)");
}
function requireDebugAuth(url2) {
  if (!DEBUG_KEY) throw new Error("DEBUG_KEY not configured");
  const key = url2.searchParams.get("key") || "";
  if (key !== DEBUG_KEY) throw new Error("Unauthorized (DEBUG_KEY)");
}
var bsdQuotaRemaining = null;
var bsdQuotaResetSeconds = null;
function updateBsdQuotaState(res) {
  const raw = res.headers.get("RateLimit") || "";
  const remainingMatch = raw.match(/(?:^|;)\s*r=(\d+)/i);
  const resetMatch = raw.match(/(?:^|;)\s*t=(\d+)/i);
  if (remainingMatch) bsdQuotaRemaining = safeNumber(remainingMatch[1], null);
  if (resetMatch) bsdQuotaResetSeconds = safeNumber(resetMatch[1], null);
}
function bsdStatsCallBudget() {
  const configured = BSD_STATS_MAX_CALLS_PER_REFRESH;
  if (bsdQuotaRemaining == null) return configured;
  const usable = bsdQuotaRemaining - BSD_STATS_QUOTA_RESERVE;
  if (usable <= 0) return 0;
  if (usable < 250) return 1;
  if (usable < 700) return Math.min(2, configured);
  return configured;
}
async function fetchBSD(endpoint, params) {
  if (!BSD_API_TOKEN) throw new Error("BSD_API_TOKEN missing");
  const url2 = new URL(`${BSD_API_BASE}${endpoint}`);
  const finalParams = { ...params || {} };
  for (const [k, v] of Object.entries(finalParams)) {
    if (v != null && v !== "") url2.searchParams.set(k, v);
  }
  const res = await fetch(url2.toString(), {
    headers: { Authorization: `Token ${BSD_API_TOKEN}` }
  });
  updateBsdQuotaState(res);
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    const err = new Error(
      `BSD API error (${res.status}): ${errorBody || res.statusText}`
    );
    err.status = res.status;
    err.body = errorBody;
    throw err;
  }
  return res.json();
}
function isBSDQuotaError(error) {
  const status2 = safeNumber(error?.status, 0);
  const message = String(error?.message || error?.body || "").toLowerCase();
  return status2 === 429 || message.includes("taster_exhausted") || message.includes("quota") || message.includes("rate limit");
}
function bsdResults(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}
async function fetchBSDCoverage() {
  try {
    const res = await fetch(BSD_COVERAGE_URL, {
      headers: { "Accept": "application/json" }
    });
    if (!res.ok) return null;
    const payload = await res.json();
    if (Array.isArray(payload?.sports)) {
      return payload.sports.find((x) => String(x?.sport).toLowerCase() === "football") || null;
    }
    return payload;
  } catch (e) {
    console.warn("BSD coverage unavailable (ignored):", e);
    return null;
  }
}
function isFinishedEvent(ev) {
  const status2 = String(ev?.status || "").toLowerCase();
  const period = String(ev?.period || "").toUpperCase();
  return status2 === "finished" || period === "FT";
}
function isDuplicateKeyError(err) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return code === "23505" || msg.includes("duplicate key value violates unique constraint") || msg.includes("live_predictions_unique_idx");
}
function isUndefinedColumnError(err) {
  const code = String(err?.code || "");
  const msg = String(err?.message || "");
  return code === "42703" || msg.toLowerCase().includes("does not exist");
}
async function insertNotification(payload) {
  const baseRow = {
    user_id: payload.user_id ?? "all",
    type: payload.type,
    title: payload.title,
    message: payload.message,
    created_at: (/* @__PURE__ */ new Date()).toISOString()
  };
  const fullRow = {
    ...baseRow,
    priority: payload.priority ?? "normal",
    read: payload.read ?? false,
    related_prediction_id: payload.related_prediction_id == null ? null : String(payload.related_prediction_id)
  };
  {
    const { error } = await supabase.from("notifications").insert(fullRow);
    if (!error) return true;
    console.error("\u274C notifications insert failed (full):", error, "row=", fullRow);
    const { error: e2 } = await supabase.from("notifications").insert(baseRow);
    if (!e2) return true;
    console.error("\u274C notifications insert failed (minimal):", e2, "row=", baseRow);
    return false;
  }
}
function formatLivePredictionType(type) {
  if (type === "total_corners") return "Corners";
  if (type === "total_shots") return "Tirs";
  if (type === "total_fouls") return "Fautes";
  return "Signal LIVE";
}
function formatThreshold(value) {
  const n = safeNumber(value, 0);
  return Number.isInteger(n) ? String(n) : String(n).replace(".", ",");
}
function predictionLabelForCaption(type) {
  if (type === "total_corners") return "corners";
  if (type === "total_shots") return "tirs";
  if (type === "total_fouls") return "fautes";
  return "";
}
function getTeamInitials(name) {
  const clean2 = String(name ?? "").replace(/[^\p{L}\p{N}\s]/gu, " ").replace(/\s+/g, " ").trim();
  if (!clean2) return "MX";
  const parts = clean2.split(" ").filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
}
function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 32768;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}
function detectImageMime(bytes) {
  if (bytes.length >= 8 && bytes[0] === 137 && bytes[1] === 80 && bytes[2] === 78 && bytes[3] === 71) {
    return "image/png";
  }
  if (bytes.length >= 3 && bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255) {
    return "image/jpeg";
  }
  return "";
}
function fitText(text2, max = 32) {
  const s = String(text2 ?? "").replace(/\s+/g, " ").trim();
  if (s.length <= max) return s;
  return s.slice(0, Math.max(0, max - 1)).trim() + "\u2026";
}
function uniqueLogoCandidates(values2) {
  return [...new Set(
    values2.map((value) => String(value ?? "").trim()).filter(Boolean)
  )];
}
function pickLogoUrls(match, type) {
  const raw = match?.raw_data || match || {};
  if (type === "home") {
    return uniqueLogoCandidates([
      match?.home_logo,
      raw?.home_logo,
      raw?.home_team_obj?.logo,
      raw?.home_team_obj?.image,
      raw?.home_team_obj?.crest,
      raw?.home?.logo,
      raw?.home?.image,
      raw?.home?.team?.logo,
      raw?.home?.team?.image,
      raw?.home?.team?.logos?.[0]?.href,
      raw?.home?.team?.logos?.[0]?.url
    ]);
  }
  if (type === "away") {
    return uniqueLogoCandidates([
      match?.away_logo,
      raw?.away_logo,
      raw?.away_team_obj?.logo,
      raw?.away_team_obj?.image,
      raw?.away_team_obj?.crest,
      raw?.away?.logo,
      raw?.away?.image,
      raw?.away?.team?.logo,
      raw?.away?.team?.image,
      raw?.away?.team?.logos?.[0]?.href,
      raw?.away?.team?.logos?.[0]?.url
    ]);
  }
  return uniqueLogoCandidates([
    match?.league_logo,
    raw?.league_logo,
    raw?.league?.logo,
    raw?.league?.image,
    raw?.league?.logos?.[0]?.href,
    raw?.competition?.logo,
    raw?.competition?.image,
    raw?.competition?.logos?.[0]?.href
  ]);
}
function pickBsdLogoIds(match, type) {
  const raw = match?.raw_data || match || {};
  const source = String(raw?.source ?? match?.source_name ?? "").toLowerCase();
  const sources = Array.isArray(raw?.merge_meta?.sources) ? raw.merge_meta.sources.map((s) => String(s).toLowerCase()) : [];
  const espnOnly = source === "espn" || sources.length === 1 && sources[0] === "espn";
  if (espnOnly) return [];
  if (type === "home") {
    return uniqueLogoCandidates([
      match?.home_team_id,
      raw?.home_team_id,
      raw?.home_team_obj?.api_id,
      raw?.home_team_obj?.id,
      raw?.home?.team?.api_id,
      raw?.home?.team?.id,
      raw?.home?.id
    ]);
  }
  if (type === "away") {
    return uniqueLogoCandidates([
      match?.away_team_id,
      raw?.away_team_id,
      raw?.away_team_obj?.api_id,
      raw?.away_team_obj?.id,
      raw?.away?.team?.api_id,
      raw?.away?.team?.id,
      raw?.away?.id
    ]);
  }
  return uniqueLogoCandidates([
    match?.league_id,
    raw?.league_id,
    raw?.league?.api_id,
    raw?.league?.id,
    raw?.competition?.api_id,
    raw?.competition?.id
  ]);
}
function pickEspnLogoId(match, type) {
  const raw = match?.raw_data || match || {};
  const source = String(raw?.source ?? match?.source_name ?? "").toLowerCase();
  const espnOnly = source === "espn" || Array.isArray(raw?.merge_meta?.sources) && raw.merge_meta.sources.length === 1 && raw.merge_meta.sources[0] === "espn";
  if (type === "home") {
    return raw?.home_team_obj?.espn_id ?? raw?.home?.team?.espn_id ?? (espnOnly ? match?.home_team_id ?? raw?.home_team_id ?? raw?.home_team_obj?.id ?? raw?.home_team_obj?.api_id : null) ?? null;
  }
  if (type === "away") {
    return raw?.away_team_obj?.espn_id ?? raw?.away?.team?.espn_id ?? (espnOnly ? match?.away_team_id ?? raw?.away_team_id ?? raw?.away_team_obj?.id ?? raw?.away_team_obj?.api_id : null) ?? null;
  }
  return raw?.league?.espn_id ?? (espnOnly ? match?.league_id ?? raw?.league_id ?? raw?.league?.id : null) ?? null;
}
function teamNameForLogo(match, kind) {
  if (kind === "home") return String(match?.home_team ?? match?.homeTeam ?? "").trim();
  if (kind === "away") return String(match?.away_team ?? match?.awayTeam ?? "").trim();
  return String(getLeagueName(match) || "").trim();
}
var telegramLogoDataCache = /* @__PURE__ */ new Map();
async function bytesToSupportedDataUri(bytes, sourceLabel = "image") {
  if (bytes.length > 8e5) {
    console.warn("Logo trop lourd, ignor\xE9:", sourceLabel, bytes.length);
    return "";
  }
  const mime = detectImageMime(bytes);
  if (!mime) {
    console.warn("Logo ignor\xE9: format non support\xE9 directement par le rendu Telegram:", sourceLabel, {
      bytes: bytes.length,
      header: Array.from(bytes.slice(0, 12)).map((b2) => b2.toString(16).padStart(2, "0")).join(" ")
    });
    return "";
  }
  return `data:${mime};base64,${bytesToBase64(bytes)}`;
}
function normalizeLogoUrl(url2) {
  const raw = String(url2 ?? "").trim();
  if (!raw) return "";
  if (raw.startsWith("data:image/")) return raw;
  if (raw.startsWith("//")) return `https:${raw}`;
  try {
    if (/^https?:\/\//i.test(raw)) return raw;
    return new URL(raw, `${BSD_API_BASE}/`).toString();
  } catch {
    return raw;
  }
}
async function fetchLogoResponse(url2, headers = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6e3);
  try {
    return await fetch(url2, {
      signal: controller.signal,
      redirect: "follow",
      headers: {
        "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
        "Accept": "image/png,image/jpeg,*/*;q=0.5",
        ...headers
      }
    });
  } finally {
    clearTimeout(timeout);
  }
}
async function convertPublicImageToPngDataUri(url2) {
  if (!/^https?:\/\//i.test(url2) || url2.includes("wsrv.nl/")) return "";
  try {
    const proxy = new URL("https://wsrv.nl/");
    proxy.searchParams.set("url", url2);
    proxy.searchParams.set("output", "png");
    proxy.searchParams.set("w", "256");
    proxy.searchParams.set("h", "256");
    proxy.searchParams.set("fit", "inside");
    const res = await fetchLogoResponse(proxy.toString());
    if (!res.ok) {
      console.warn("Conversion PNG logo impossible:", res.status, url2);
      return "";
    }
    const bytes = new Uint8Array(await res.arrayBuffer());
    return await bytesToSupportedDataUri(bytes, `png-proxy:${url2}`);
  } catch (e) {
    console.warn("Conversion PNG logo impossible:", url2, e);
    return "";
  }
}
async function imageUrlToDataUri(url2) {
  const normalized = normalizeLogoUrl(url2);
  if (!normalized) return "";
  if (normalized.startsWith("data:image/")) return normalized;
  const cacheKey = `url:${normalized}`;
  const cached = telegramLogoDataCache.get(cacheKey);
  if (cached) return cached;
  try {
    const res = await fetchLogoResponse(normalized);
    if (!res.ok) {
      console.warn("Logo impossible \xE0 charger:", res.status, normalized);
      return "";
    }
    const bytes = new Uint8Array(await res.arrayBuffer());
    const direct = await bytesToSupportedDataUri(bytes, normalized);
    if (direct) {
      telegramLogoDataCache.set(cacheKey, direct);
      return direct;
    }
    const converted = await convertPublicImageToPngDataUri(normalized);
    if (converted) telegramLogoDataCache.set(cacheKey, converted);
    return converted;
  } catch (e) {
    const detail = e?.name === "AbortError" ? "timeout" : e?.message || String(e);
    console.warn("Logo impossible \xE0 convertir en data URI:", normalized, detail);
    return "";
  }
}
async function bsdImageToDataUri(type, id) {
  if (!id || !BSD_API_TOKEN) return "";
  const safeId = String(id).trim();
  if (!safeId) return "";
  const cacheKey = `bsd:${type}:${safeId}`;
  const cached = telegramLogoDataCache.get(cacheKey);
  if (cached) return cached;
  try {
    const url2 = `${BSD_IMG_BASE}/${type}/${encodeURIComponent(safeId)}/`;
    const res = await fetchLogoResponse(url2, { Authorization: `Token ${BSD_API_TOKEN}` });
    if (!res.ok) {
      console.warn("Logo BSD impossible \xE0 charger:", res.status, type, safeId);
      return "";
    }
    const bytes = new Uint8Array(await res.arrayBuffer());
    const direct = await bytesToSupportedDataUri(bytes, `${type}:${safeId}`);
    if (direct) {
      telegramLogoDataCache.set(cacheKey, direct);
      return direct;
    }
    if (SUPABASE_URL) {
      const publicProxy = `${SUPABASE_URL.replace(/\/$/, "")}/functions/v1/live/img/${type}/${encodeURIComponent(safeId)}/`;
      const converted = await convertPublicImageToPngDataUri(publicProxy);
      if (converted) {
        telegramLogoDataCache.set(cacheKey, converted);
        return converted;
      }
    }
    return "";
  } catch (e) {
    const detail = e?.name === "AbortError" ? "timeout" : e?.message || String(e);
    console.warn("Logo BSD impossible \xE0 convertir:", type, safeId, detail);
    return "";
  }
}
function espnTeamLogoUrl(id) {
  const clean2 = String(id ?? "").trim();
  return clean2 ? `https://a.espncdn.com/i/teamlogos/soccer/500/${encodeURIComponent(clean2)}.png` : "";
}
async function getTelegramLogoData(match, kind) {
  for (const directUrl of pickLogoUrls(match, kind)) {
    const direct = await imageUrlToDataUri(directUrl);
    if (direct) return direct;
  }
  for (const id of pickBsdLogoIds(match, kind)) {
    const bsd = await bsdImageToDataUri(kind === "league" ? "league" : "team", id);
    if (bsd) return bsd;
  }
  if (kind !== "league") {
    const espnId = pickEspnLogoId(match, kind);
    if (espnId) {
      const espn = await imageUrlToDataUri(espnTeamLogoUrl(espnId));
      if (espn) return espn;
    }
  }
  console.warn("\u26A0\uFE0F Aucun logo exploitable pour Telegram:", {
    kind,
    team: teamNameForLogo(match, kind),
    match_id: match?.id ?? null,
    source: match?.raw_data?.source ?? match?.source_name ?? null
  });
  return "";
}
var telegramResvgModulePromise = null;
async function loadTelegramResvgModule() {
  if (!telegramResvgModulePromise) {
    telegramResvgModulePromise = Promise.resolve().then(() => (init_resvg_wasm(), resvg_wasm_exports)).then((mod) => ({
      initWasm: mod.initWasm,
      Resvg: mod.Resvg
    })).catch((e) => {
      telegramResvgModulePromise = null;
      throw e;
    });
  }
  return await telegramResvgModulePromise;
}
var resvgReady = null;
var REMOTE_FONT_URLS = {
  "NotoSans-Regular.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
  ],
  "NotoSans-Bold.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf"
  ],
  "NotoSans-ExtraBold.ttf": [
    "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-ExtraBold.ttf",
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-ExtraBold.ttf"
  ]
};
function fontHeader(bytes) {
  return Array.from(bytes.slice(0, 16)).map((b2) => b2.toString(16).padStart(2, "0")).join(" ");
}
function isValidFontFile(bytes) {
  if (bytes.byteLength < 2e4) return false;
  const head = Array.from(bytes.slice(0, 4)).map((b2) => b2.toString(16).padStart(2, "0")).join("");
  return head === "00010000" || head === "4f54544f" || head === "74746366" || head === "74727565";
}
function toExactArrayBuffer(bytes) {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy.buffer;
}
async function fetchRemoteFont(filename) {
  const urls = REMOTE_FONT_URLS[filename] || [];
  if (!urls.length) throw new Error(`Aucune URL distante pour ${filename}`);
  const errors = [];
  for (const url2 of urls) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8e3);
    try {
      const res = await fetch(url2, {
        signal: controller.signal,
        headers: {
          "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
          "Accept": "font/ttf,application/octet-stream,*/*;q=0.8"
        }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bytes = new Uint8Array(await res.arrayBuffer());
      if (!isValidFontFile(bytes)) {
        throw new Error(`fichier police invalide (${bytes.byteLength} octets, header=${fontHeader(bytes)})`);
      }
      console.log("\u2705 Police Telegram distante charg\xE9e", {
        filename,
        bytes: bytes.byteLength,
        source: url2.includes("jsdelivr") ? "jsDelivr" : "GitHub"
      });
      return bytes;
    } catch (e) {
      const detail = e?.name === "AbortError" ? "timeout" : e?.message || String(e);
      errors.push(`${url2} => ${detail}`);
      console.warn("\u26A0\uFE0F Source de police indisponible", { filename, source: url2, error: detail });
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new Error(`Impossible de charger ${filename}: ${errors.join(" | ")}`);
}
async function readBundledTelegramFont(filename) {
  try {
    const url2 = new URL(`./_fonts/${filename}`, import.meta.url);
    const bytes = await Deno.readFile(url2);
    if (!isValidFontFile(bytes)) {
      throw new Error(
        `police locale invalide (${bytes.byteLength} octets, header=${fontHeader(bytes)})`
      );
    }
    console.log("\u2705 Police Telegram locale charg\xE9e", {
      filename,
      bytes: bytes.byteLength
    });
    return bytes;
  } catch (e) {
    console.warn(
      "\u26A0\uFE0F Police locale indisponible, fallback distant:",
      filename,
      e?.message || String(e)
    );
    return await fetchRemoteFont(filename);
  }
}
async function fetchResvgWasm() {
  const urls = [
    "https://cdn.jsdelivr.net/npm/@resvg/resvg-wasm@2.6.2/index_bg.wasm",
    "https://unpkg.com/@resvg/resvg-wasm@2.6.2/index_bg.wasm",
    "https://esm.sh/@resvg/resvg-wasm@2.6.2/index_bg.wasm"
  ];
  const errors = [];
  for (const url2 of urls) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1e4);
    try {
      const res = await fetch(url2, {
        signal: controller.signal,
        headers: {
          "User-Agent": "Mozilla/5.0 MrXPRONOS-Live-Telegram/1.0",
          "Accept": "application/wasm,application/octet-stream,*/*;q=0.8"
        }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bytes = await res.arrayBuffer();
      if (bytes.byteLength < 1e4) {
        throw new Error(`WASM anormalement petit (${bytes.byteLength} octets)`);
      }
      console.log("\u2705 resvg WASM charg\xE9", { url: url2, bytes: bytes.byteLength });
      return bytes;
    } catch (e) {
      const detail = e?.name === "AbortError" ? "timeout 10s" : e?.message || String(e);
      errors.push(`${url2} => ${detail}`);
      console.warn("\u26A0\uFE0F \xC9chec chargement resvg WASM, essai CDN suivant:", url2, detail);
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new Error(`Impossible de charger resvg WASM. ${errors.join(" | ")}`);
}
async function ensureResvgReady() {
  if (!resvgReady) {
    resvgReady = (async () => {
      const { initWasm: initWasm2 } = await loadTelegramResvgModule();
      const wasmBytes = await fetchResvgWasm();
      await initWasm2(wasmBytes);
      console.log("\u2705 resvg initialis\xE9 pour les images Telegram");
    })();
  }
  try {
    await resvgReady;
  } catch (e) {
    resvgReady = null;
    throw e;
  }
}
function formatTelegramSlipDateTime(match) {
  const raw = getMatchEventDate(match);
  const d = raw ? new Date(raw) : /* @__PURE__ */ new Date();
  if (!Number.isFinite(d.getTime())) {
    return "--.--.---- (--:--)";
  }
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = String(d.getFullYear());
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${day}.${month}.${year} (${hours}:${minutes})`;
}
function formatTelegramClock(value) {
  const minute = Math.max(0, safeNumber(value, 0));
  const whole = Math.floor(minute);
  let seconds = Math.round((minute - whole) * 60);
  let mins = whole;
  if (seconds >= 60) {
    mins += 1;
    seconds = 0;
  }
  return `${mins}:${String(seconds).padStart(2, "0")}`;
}
function pickTelegramNumber(...values2) {
  for (const value of values2) {
    if (value == null || value === "") continue;
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}
function formatTelegramMoney(value) {
  if (value == null) return "\u2014";
  const amount = Math.round(Math.max(0, value));
  return `${amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ")} F`;
}
function escapeXml(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");
}
var telegramVectorFontsPromise = null;
async function getTelegramVectorFonts() {
  if (!telegramVectorFontsPromise) telegramVectorFontsPromise = (async () => {
    const module = await Promise.resolve().then(() => __toESM(require_opentype()));
    const op = module.default?.parse ? module.default : module;
    const fontBytes = await Promise.all([
      readBundledTelegramFont("NotoSans-Regular.ttf"),
      readBundledTelegramFont("NotoSans-Bold.ttf")
    ]);
    const fonts = { regular: toExactArrayBuffer(fontBytes[0]), bold: toExactArrayBuffer(fontBytes[1]) };
    async function parse2(bytes, name) {
      try {
        const f = op.parse(bytes.slice(0));
        if (!f?.unitsPerEm) throw Error("no glyphs");
        return f;
      } catch (e) {
        console.warn("Police locale rejet\xE9e, r\xE9cup\xE9ration source distante:", name, e?.message);
        const clean2 = await fetchRemoteFont(name);
        return op.parse(toExactArrayBuffer(clean2));
      }
    }
    const [regular, bold] = await Promise.all([
      parse2(fonts.regular, "NotoSans-Regular.ttf"),
      parse2(fonts.bold, "NotoSans-Bold.ttf")
    ]);
    return { regular, bold };
  })().catch((e) => {
    telegramVectorFontsPromise = null;
    throw e;
  });
  return await telegramVectorFontsPromise;
}
function telegramVectorText(font, x, y, raw, size2, color, anchor) {
  const str = String(raw ?? "");
  const width = font.getAdvanceWidth(str, size2, { kerning: true });
  const left = anchor === "end" ? x - width : anchor === "middle" ? x - width / 2 : x;
  const data = font.getPath(str, left, y, size2, { kerning: true }).toPathData(2);
  return '<path fill="' + color + '" d="' + data + '"/>';
}
async function buildTelegramCouponPngDirect(match, pred) {
  const { Resvg: Resvg3 } = await loadTelegramResvgModule();
  await ensureResvgReady();
  const vectorFonts = await getTelegramVectorFonts();
  const esc = escapeXml;
  const dt = pred?.created_at ? new Date(pred.created_at) : /* @__PURE__ */ new Date();
  const date2 = Number.isFinite(dt.getTime()) ? dt.toLocaleDateString("fr-FR", { timeZone: "UTC" }) + " (" + dt.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + ")" : formatTelegramSlipDateTime(match);
  const minute = safeNumber(pred?.signal_minute ?? pred?.minute ?? match?.current_minute ?? match?.minute, 0);
  const home = fitText(match?.home_team ?? "\xC9quipe A", 18);
  const away = fitText(match?.away_team ?? "\xC9quipe B", 18);
  const league = fitText(getLeagueName(match), 33);
  const raw = { signal_half1_home: pred?.signal_half1_home, signal_half1_away: pred?.signal_half1_away, signal_half2_home: pred?.signal_half2_home, signal_half2_away: pred?.signal_half2_away };
  const getNum = (...values2) => {
    for (const v of values2) if (v !== null && v !== void 0 && v !== "" && Number.isFinite(Number(v))) return Number(v);
    return null;
  };
  const h1 = getNum(raw?.signal_half1_home);
  const a1 = getNum(raw?.signal_half1_away);
  const h2 = getNum(raw?.signal_half2_home);
  const a2 = getNum(raw?.signal_half2_away);
  const homeScore = h1 !== null && h2 !== null ? h1 + h2 : safeNumber(pred?.signal_home_score ?? pred?.home_score ?? match?.home_score, 0);
  const awayScore = a1 !== null && a2 !== null ? a1 + a2 : safeNumber(pred?.signal_away_score ?? pred?.away_score ?? match?.away_score, 0);
  const periodText = h1 !== null && a1 !== null ? h2 !== null && a2 !== null ? homeScore + ":" + awayScore + " (" + h1 + ":" + a1 + "," + h2 + ":" + a2 + ")" : homeScore + ":" + awayScore + " (" + h1 + ":" + a1 + ")" : "";
  const odds = pickTelegramNumber(pred?.live_odds, pred?.odds, pred?.odd, pred?.cote);
  const oddsLabel = pred?.pricing_mode === "external_live" ? "Cote bookmaker" : "Cote mod\xE8le";
  const stake = LIVE_COUPON_STAKE_FCFA;
  const potential = odds !== null && odds > 1 ? Math.round(stake * odds) : null;
  const value = (v) => v === null ? "\u2014" : v.toFixed(2);
  const money = (v) => v === null ? "\u2014" : Math.round(v).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ") + " F";
  const slip = String(pred?.id ?? pred?.prediction_id ?? match?.id ?? "").replace(/[^a-zA-Z0-9]/g, "").slice(-11);
  const threshold = formatThreshold(pred?.threshold ?? pred?.pronostic ?? pred?.line ?? "");
  const type = formatLivePredictionType(String(pred?.prediction_type ?? pred?.type ?? ""));
  const selection = "Total. (" + threshold + ") Plus de. " + type;
  const validationOutcome = pred?.__validationOutcome ?? null;
  const receiptStatus = validationOutcome === "success" ? "Pay\xE9" : validationOutcome === "failure" ? "Perdu" : "Accept\xE9";
  const slipStatus = validationOutcome === "success" ? "Gain" : validationOutcome === "failure" ? "Perdu" : "Accept\xE9";
  const statusColor = validationOutcome === "success" ? "#33a766" : validationOutcome === "failure" ? "#df4545" : "#4f96d7";
  const [homeLogo, awayLogo] = await Promise.all([
    getTelegramLogoData(match, "home"),
    getTelegramLogoData(match, "away")
  ]);
  const football = (x, y, sz) => '<image href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAFF0lEQVR42u1VW2xUVRRd+5y5986LPqZDW8pDkFKKlacFIYApMUBi8Es7H0ZJ0AQT44/GaPTDdj410R/Dh/ERxejHHYwaYwg+QiMGQRSwUKCAUGg70NJ5dQZm7r3nnu1HLZZnSPx155yPk5ystc86e+9FuEswsyQif/L84de/NJWvFZrIEOVIPPjXtg0bKpP3AGgi4psxxJ3AO21bEpG/Z8/RyFhJbfti977v8vkrx5TyDngV94/CcOnI4f6ht0ZKvJSIfCJiZqZ7IrCZZSqR8LMlb8vKdYuPpEezH4/lxx+TgmJaawmtLa391vPpkVeVUz48WvR2MHOYiLirq+sGzFsYbduWiUTC/2DX9y821E9/zzICCAjhHeo9TpZpCmYmEoId1+PGeEzPnzNLllwlCoXC/uHC+OMvd27OAcCkXHQ78Hd2fvVE0ArtKhXHVbniYG37MpnJFXD6/AWEghZ8rSGEwPr25TjU24fc+Lgbj0+3nPLVvYVztZuADp1MEgNgOeVDqa2tjZtaHop7GrtZ+yECwTACMpMrYFHzPDAzIqEQQpaJ1vlzkR4ZRSQckp7jeJFpVc1GpJh9/aVFB2zblqlUiq/r1d3TI4mI8473XCgcme56ns9gQUTwlAIJQkO8DvHaGkyvi6F6WhRlxwERgZnBIFkpl7Wn1Svbu94PJxIJDYBoSk2SlJI/+7bn4Eg2t1L7vk+ALDsOlrQuQKXi4OiJ0wgGLfi+RjgUxNr2pTh49Dh834cQAspTOhaLyaWtCzauarvvR5tZikl5gQ34+teLC1OWgYpHxfeEohVl2NaCSC0wODmBaNwDQMhMNBlCsOBtMjaJk3B67rgZnhKaWXPNDC82bPWAEAnQAFAKB74rN5oP9ydU1NKPLw8sXI5PLQmtEYj+FwXz+U8iEtAc0a8AHLDODshUFsWr8aa9uXwfU8SCExf84sKhbG6yaFmSTgJIDmWY3ldC7j9Z48beWLJYAZV7I5NDXEcTF9GQTCxCI4rotZjQ3IjxdxrP8sTCMA11Ooi9dxY13N1RsabbJmIxGM9Z46M3wlV2DX9dhTCgNDw5BCYE5TA8ZLJbiuh3KlAiJC89zZ6D83AMf1UHZcOK5LR/pOUfrSlRMA0NPTM/ECAOjq2hsgIvX2R6mfotGqhVevFbUACcs00XfmHNqXtCESCgEEKOVjRn0co5ksiqVrCFomtNYctCwxlhkrfjN08WcA6Ojo8Ke0dYcGAMs0djhOWUkSREIwM8MIBCAEQbO+vn2tYZkmGAwiAkAqFI4IKeSnyRe2jtoTs4xv28nvfvJlMhStejOXzTi+r41HVq2ggaFhDAylYRoGmAEGo2N1O473n8Wl0TFVVVVlgHnQgF4+du7PXHd3N99CAIBsm0UiIfzUD/t3NjY0PONVyr6nlP792EkZskzSPJGxUopra6p56cIWv1ipmEqpsYuD6Y3bE5uPdjGLJJG+XkVTLaCzE7qLtXjKMLYOZ64OCSlfu5geMYxAAJpZA6yZiZghp0WjaFkwVyrPPxiPymdpzeITtm3LxBQPuWVcExEnAfaUovpq641MNr9mZmP9502N9SMkhAiGwgHLsqRpmZXW++f+qlzv+Se3PLqOiE5MSjwVL3Bbt/mnbG1muZDoNwBP7+u9UJvJlhZqz61Tksrxhtrzy1tmnp8yLMVU97vnYGZh879T9+ZUmFnezsnuaDh3IaJUKnVd0r6+Pk4mkxr/x3+NvwHWHqQSNvXFqQAAAABJRU5ErkJggg==" x="' + x + '" y="' + y + '" width="' + sz + '" height="' + sz + '"/>';
  const circle = (logo, x, name) => logo ? '<image href="' + logo + '" x="' + x + '" y="282" width="34" height="34" preserveAspectRatio="xMidYMid meet"/>' : '<circle cx="' + (x + 17) + '" cy="299" r="16" fill="#eff2f4" stroke="#a8b6c2"/>' + telegramVectorText(vectorFonts.bold, x + 17, 303, getTeamInitials(name), 9, "#1e3645", "middle");
  const tx = (x, y, txt, size2, color = "#1c3242", weight = 700, anchor = "start") => telegramVectorText(weight >= 700 ? vectorFonts.bold : vectorFonts.regular, x, y, txt, size2, color, anchor);
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="429" height="455" viewBox="0 0 429 455"><rect width="429" height="455" rx="9" fill="#fff" stroke="#dbe0e5"/><circle cx="42" cy="48" r="25" fill="#ecf1f4"/>' + football(29, 35, 26) + '<circle cx="62" cy="69" r="9" fill="#29b36c"/><path d="M58 69l3 3 5-7" fill="none" stroke="white" stroke-width="1.7"/>' + tx(80, 34, date2, 12, "#8698a6") + tx(80, 55, "Simple", 19) + tx(80, 72, "N\xB0 " + slip, 10, "#24313a", 600) + '<rect x="348" y="24" width="67" height="14" rx="3" fill="#ef4338"/>' + tx(381.5, 34, "\u2022 En direct", 9, "#fff", 700, "middle") + '<path d="M0 87h429" stroke="#e4e8eb"/>' + tx(16, 113, oddsLabel + ":", 15, "#8497a5") + tx(16, 141, "Mise:", 15, "#8497a5") + tx(16, 167, "Gains potentiels:", 15, "#8497a5") + tx(16, 193, "Statut:", 15, "#8497a5") + tx(414, 113, value(odds), 15, "#1c3242", 700, "end") + tx(414, 141, money(stake), 15, "#1c3242", 700, "end") + tx(414, 167, money(potential), 15, "#4dbb69", 700, "end") + tx(414, 193, receiptStatus, 15, statusColor, 700, "end") + '<path d="M0 211h429" stroke="#eff3f5" stroke-width="8"/><rect x="7" y="219" width="415" height="234" rx="11" fill="#fbfbfb" stroke="#d9e1e7"/>' + football(18, 235, 24) + tx(52, 245, "Football \xB7 " + league, 12, "#8599a7") + tx(52, 262, date2, 12, "#8599a7") + '<rect x="352" y="226" width="67" height="13" rx="3" fill="#ef4338"/>' + tx(385.5, 235, "\u2022 En direct", 9, "#fff", 700, "middle") + tx(139, 304, home, 13, "#20323f", 700, "end") + circle(homeLogo, 150, home) + tx(216, 305, homeScore + ":" + awayScore, 19, "#20323f", 800, "middle") + circle(awayLogo, 249, away) + tx(292, 304, away, 13, "#20323f") + tx(216, 351, periodText, 12, "#879da9", 400, "middle") + '<path d="M8 363h414" stroke="#dbe1e6"/>' + tx(19, 383, selection, 13, "#24333e", 700) + tx(412, 383, value(odds), 14, "#24333e", 700, "end") + tx(19, 410, "EN DIRECT", 13, "#869aa7") + tx(412, 410, "temps \xE9coul\xE9 : " + formatTelegramClock(minute), 13, "#24333e", 700, "end") + tx(19, 439, "Statut:", 13, "#869aa7") + tx(412, 439, slipStatus, 13, statusColor, 700, "end") + "</svg>";
  const renderer = new Resvg3(svg, { fitTo: { mode: "original" } });
  const png = renderer.render().asPng();
  if (!png || png.byteLength < 1500) throw new Error("PNG SVG Telegram invalide");
  return png;
}
function buildTelegramText(match, pred) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? ""
  );
  const label = predictionLabelForCaption(type);
  return `\u{1F525} NOUVEAU COUPON LIVE

\u26BD\uFE0F Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}
function telegramChatIds() {
  return [...new Set(
    [TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID_SECONDARY].map((id) => String(id || "").trim()).filter(Boolean)
  )];
}
function sanitizeTelegramTargets(targetChatIds) {
  const allowed = telegramChatIds();
  if (!targetChatIds?.length) return allowed;
  const allowedSet = new Set(allowed);
  const requested = [...new Set(
    targetChatIds.map((id) => String(id || "").trim()).filter(Boolean)
  )];
  const filtered = requested.filter((id) => allowedSet.has(id));
  return filtered.length ? filtered : allowed;
}
async function sendTelegramPhoto(pngBytes, caption, buttonUrl, targetChatIds) {
  const chatIds = sanitizeTelegramTargets(targetChatIds);
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    const message = "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant";
    console.warn(`Telegram non configur\xE9: ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: chatIds, error: message };
  }
  if (!chatIds.length) {
    const message = "aucun canal Telegram cible";
    console.warn(`Telegram non configur\xE9: ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: [], error: message };
  }
  const pngSignature = [137, 80, 78, 71, 13, 10, 26, 10];
  const validPng = pngBytes.byteLength > 1e3 && pngSignature.every((value, index) => pngBytes[index] === value);
  if (!validPng) {
    const message = `PNG Telegram invalide (${pngBytes.byteLength} octets)`;
    console.error(`\u274C ${message}`);
    return { ok: false, sentChatIds: [], failedChatIds: chatIds, error: message };
  }
  console.log("\u{1F5BC}\uFE0F Image Telegram pr\xEAte", { bytes: pngBytes.byteLength, chatIds });
  const sentChatIds = [];
  const failedChatIds = [];
  const errors = [];
  for (const chatId of chatIds) {
    let sent = false;
    let lastError = "";
    for (let attempt = 1; attempt <= 2; attempt++) {
      const form = new FormData();
      form.append("chat_id", chatId);
      if (caption && caption.trim()) form.append("caption", caption);
      if (buttonUrl) {
        form.append(
          "reply_markup",
          JSON.stringify({
            inline_keyboard: [
              [
                {
                  text: "Voir plus de coupons \u{1F525}",
                  url: "https://mrxpronos.github.io/MrXPRONOS_App/live.html"
                }
              ],
              [
                {
                  text: "S\u2019inscrire ou r\xE9initialiser son compte \u{1F3AF}",
                  url: "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html"
                }
              ]
            ]
          })
        );
      }
      form.append(
        "photo",
        new Blob([toExactArrayBuffer(pngBytes)], { type: "image/png" }),
        `coupon-live-${Date.now()}-${attempt}.png`
      );
      try {
        const res = await richPhotoOrLegacy(
          TELEGRAM_BOT_TOKEN,
          chatId,
          pngBytes,
          caption,
          buttonUrl ? [
            [{ text: "Voir plus de coupons \u{1F525}", url: "https://mrxpronos.github.io/MrXPRONOS_App/live.html", style: "primary" }],
            [{ text: "S\u2019inscrire ou r\xE9initialiser son compte \u{1F3AF}", url: "https://mrxpronos.github.io/MrXPRONOS_App/bookmakers.html", style: "success" }]
          ] : [],
          form,
          `coupon-live-${Date.now()}-${attempt}.png`
        );
        if (res.ok) {
          sent = true;
          sentChatIds.push(chatId);
          console.log(`\u2705 Coupon LIVE envoy\xE9 en IMAGE vers ${chatId} (tentative ${attempt})`);
          break;
        }
        const body = await res.text().catch(() => "");
        lastError = `sendPhoto ${res.status}${body ? `: ${body}` : ""}`;
        console.error(`\u274C Telegram sendPhoto failed [${chatId}] tentative ${attempt}:`, res.status, body);
      } catch (e) {
        lastError = e?.message || String(e);
        console.error(`\u274C Telegram sendPhoto exception [${chatId}] tentative ${attempt}:`, e);
      }
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!sent) {
      failedChatIds.push(chatId);
      errors.push(`${chatId} => ${lastError || "sendPhoto \xE9chou\xE9 apr\xE8s 2 tentatives"}`);
    }
  }
  return {
    ok: failedChatIds.length === 0 && sentChatIds.length === chatIds.length,
    sentChatIds,
    failedChatIds,
    error: errors.length ? errors.join(" | ") : null
  };
}
async function sendTelegramLiveCoupon(match, pred, predictionId, targetChatIds) {
  try {
    const png = await attachLiveSponsorBanner(await buildTelegramCouponPngDirect(match, {
      ...pred,
      id: predictionId ?? pred?.id
    }));
    return await sendTelegramPhoto(
      png,
      buildTelegramText(match, pred),
      "https://mrxpronos.github.io/MrXPRONOS_App/live.html",
      targetChatIds
    );
  } catch (e) {
    const err = e?.stack || e?.message || String(e);
    console.error("TELEGRAM_IMAGE_ERROR", err);
    return { ok: false, sentChatIds: [], failedChatIds: sanitizeTelegramTargets(targetChatIds), error: err };
  }
}
function validationStatusMeta(outcome) {
  if (outcome === "success") {
    return {
      emoji: "\u2705",
      header: "COUPON VALID\xC9",
      status: "R\xC9USSI",
      color: "#22C55E",
      bg: "#0f2a18",
      border: "#22C55E"
    };
  }
  return {
    emoji: "\u274C",
    header: "COUPON PERDU",
    status: "\xC9CHOU\xC9",
    color: "#EF4444",
    bg: "#2a1111",
    border: "#EF4444"
  };
}
function buildValidationCouponText(pred) {
  const type = String(pred?.prediction_type ?? pred?.type ?? "");
  const threshold = formatThreshold(
    pred?.threshold ?? pred?.pronostic ?? pred?.line ?? pred?.target_value ?? ""
  );
  const label = predictionLabelForCaption(type);
  return `Total plus de ${threshold}${label ? ` ${label}` : ""}`;
}
function splitMatchName(matchName) {
  const text2 = String(matchName ?? "").trim();
  if (!text2) return { home: "\xC9quipe A", away: "\xC9quipe B" };
  const parts = text2.split(/\s+vs\s+/i);
  if (parts.length >= 2) {
    return {
      home: parts[0].trim() || "\xC9quipe A",
      away: parts.slice(1).join(" vs ").trim() || "\xC9quipe B"
    };
  }
  return { home: text2, away: "\xC9quipe B" };
}
async function getTelegramMatchFromCache(pred, ev) {
  const { data } = await supabase.from("matches_live").select("*").eq("id", String(pred.match_id)).limit(1).maybeSingle();
  if (data) {
    return {
      id: data.id,
      home_team: data.home_team,
      away_team: data.away_team,
      home_score: data.home_score ?? 0,
      away_score: data.away_score ?? 0,
      current_minute: data.current_minute ?? 90,
      league_name: data.league_name ?? pred.league_name ?? null,
      league: { name: data.league_name ?? pred.league_name ?? "Football" },
      raw_data: data.raw_data || {},
      home_logo: data.raw_data?.home_logo ?? null,
      away_logo: data.raw_data?.away_logo ?? null,
      league_logo: data.raw_data?.league_logo ?? null
    };
  }
  const names = splitMatchName(pred?.match_name);
  return {
    id: pred.match_id,
    home_team: names.home,
    away_team: names.away,
    home_score: ev?.home_score ?? ev?.home?.score ?? 0,
    away_score: ev?.away_score ?? ev?.away?.score ?? 0,
    current_minute: 90,
    league_name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football",
    league: { name: pred?.league_name ?? ev?.league?.name ?? ev?.competition?.name ?? "Football" },
    raw_data: ev || {}
  };
}
function buildTelegramValidationText(pred, outcome, currentValue) {
  const meta = validationStatusMeta(outcome);
  const couponText = buildValidationCouponText(pred);
  return `${meta.emoji} ${outcome === "success" ? "COUPON VALID\xC9" : "COUPON PERDU"}

\u26BD\uFE0F ${couponText}
\u{1F4CA} R\xE9sultat : ${currentValue}`;
}
async function sendTelegramValidationResult(match, pred, outcome, currentValue, validationType, predictionId) {
  try {
    const snapshotPred = { ...pred, id: predictionId ?? pred?.id, __validationOutcome: outcome };
    const png = await buildTelegramCouponPngDirect(
      { ...match, current_minute: match?.current_minute ?? (validationType === "final" ? 90 : 0) },
      snapshotPred
    );
    const result = await sendTelegramPhoto(
      png,
      buildTelegramValidationText(pred, outcome, currentValue),
      "https://mrxpronos.github.io/MrXPRONOS_App/live.html"
    );
    if (!result.ok) console.error("TELEGRAM_VALIDATION_IMAGE_SEND_FAILED", result.error);
    return result.ok;
  } catch (e) {
    console.error("TELEGRAM_VALIDATION_IMAGE_FAILED", e?.stack || e?.message || String(e));
    return false;
  }
}
function computeMomentum(stats) {
  const h = stats?.home || {};
  const a = stats?.away || {};
  const hm = safeNumber(h.total_shots) * 2 + safeNumber(h.shots_on_target) * 3 + safeNumber(h.corner_kicks) * 1.5 + safeNumber(h.ball_possession) * 0.15;
  const am = safeNumber(a.total_shots) * 2 + safeNumber(a.shots_on_target) * 3 + safeNumber(a.corner_kicks) * 1.5 + safeNumber(a.ball_possession) * 0.15;
  const total = hm + am;
  const homeRatio = total > 0 ? hm / total : 0.5;
  const awayRatio = 1 - homeRatio;
  let dominant = "balanced";
  if (homeRatio >= 0.58) dominant = "home";
  else if (awayRatio >= 0.58) dominant = "away";
  return {
    total: Math.round(total),
    home_ratio: Math.round(homeRatio * 100),
    away_ratio: Math.round(awayRatio * 100),
    dominant_side: dominant
  };
}
function getTotalStats(stats) {
  return {
    shots: safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots),
    shotsOnTarget: safeNumber(stats?.home?.shots_on_target) + safeNumber(stats?.away?.shots_on_target),
    corners: safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks),
    fouls: safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls),
    possessionHome: safeNumber(stats?.home?.ball_possession),
    possessionAway: safeNumber(stats?.away?.ball_possession)
  };
}
function getMatchFlow(stats, minute, momentum) {
  const totals = getTotalStats(stats);
  const globalShotsRate = totals.shots / Math.max(minute, 1);
  const globalCornersRate = totals.corners / Math.max(minute, 1);
  const globalFoulsRate = totals.fouls / Math.max(minute, 1);
  const attackingPressure = totals.shotsOnTarget * 2 + totals.corners * 1.4 + Math.abs(totals.possessionHome - totals.possessionAway) * 0.08 + safeNumber(momentum?.total) * 0.12;
  let flow = "neutral";
  if (attackingPressure >= 18 || globalShotsRate >= 0.22 || globalCornersRate >= 0.09) {
    flow = "offensive";
  }
  if (minute >= 65 && attackingPressure < 12 && globalShotsRate < 0.18 && globalCornersRate < 0.07) {
    flow = "defensive";
  }
  return { flow, attackingPressure, globalShotsRate, globalCornersRate, globalFoulsRate };
}
function conservativeProjection(params) {
  const { current, minute, type, flow } = params;
  const elapsed = Math.max(1, minute);
  const remaining = Math.max(0, 90 - elapsed);
  const baseRate = current / elapsed;
  let multiplier = 0.72;
  if (flow === "offensive") multiplier = 0.82;
  if (flow === "neutral") multiplier = 0.7;
  if (flow === "defensive") multiplier = 0.52;
  if (minute >= 70) multiplier -= 0.08;
  if (minute >= 78) multiplier -= 0.1;
  multiplier = Math.max(0.35, multiplier);
  let projected = current + baseRate * remaining * multiplier;
  const maxExtra = type === "corners" ? 4 : type === "shots" ? 8 : 8;
  projected = Math.min(projected, current + maxExtra);
  return Number(projected.toFixed(1));
}
var LIVE_VALUE_MODEL_VERSION = "live-value-v2.3-playability-envelope";
var LIVE_MARKET_LINES = {
  corners: [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5],
  shots: [15.5, 17.5, 19.5, 21.5, 23.5, 25.5, 27.5, 29.5, 31.5, 33.5],
  fouls: [17.5, 19.5, 21.5, 23.5, 24.5, 25.5, 27.5, 29.5, 31.5]
};
var LEGACY_BASELINE_LINES = {
  corners: [7.5, 8.5, 9.5, 10.5, 11.5],
  shots: [17.5, 19.5, 21.5, 23.5, 25.5, 27.5, 29.5],
  fouls: [19.5, 21.5, 23.5, 24.5, 25.5, 27.5]
};
function legacyBaselineThreshold(type, current, projected, minGap = 2) {
  const lines = LEGACY_BASELINE_LINES[type] || [];
  return lines.find(
    (threshold) => current < threshold && threshold - current >= minGap && projected >= threshold + 0.5
  ) ?? null;
}
function historicalUpliftCap(type, minute) {
  if (type === "shots") {
    if (minute < 30) return 6;
    if (minute < 45) return 5;
    if (minute < 60) return 2;
    if (minute < 75) return 1;
    return 0;
  }
  if (type === "corners") {
    if (minute >= 30 && minute < 45) return 1;
    return 0;
  }
  return null;
}
function poissonTail(lambda, atLeast) {
  if (atLeast <= 0) return 1;
  if (!(lambda > 0)) return 0;
  let term = Math.exp(-lambda);
  let cdf = term;
  for (let k = 1; k < atLeast; k++) {
    term *= lambda / k;
    cdf += term;
  }
  return Math.min(0.995, Math.max(5e-3, 1 - cdf));
}
function marketProjectionBuffer(type) {
  if (type === "corners") return 1.5;
  if (type === "shots") return 6;
  return 3;
}
function candidateProbability(params) {
  const { current, threshold, projected, heuristicProbability, reliability } = params;
  const futureMean = Math.max(0.05, projected - current);
  const additionalNeeded = Math.max(0, Math.floor(threshold) + 1 - current);
  const countProbability = poissonTail(futureMean, additionalNeeded);
  const heuristic = Math.min(0.95, Math.max(0.2, heuristicProbability));
  const rel = Math.min(1, Math.max(0, reliability / 100));
  const blended = countProbability * 0.72 + heuristic * 0.18 + 0.5 * 0.1;
  const calibrated = 0.5 + (blended - 0.5) * (0.72 + rel * 0.28);
  return Number(Math.min(0.94, Math.max(0.18, calibrated)).toFixed(4));
}
function estimatedModelOdds(probability) {
  const p = Math.min(0.95, Math.max(0.05, probability));
  return Number((1 / p).toFixed(2));
}
function selectMedianCandidate(items) {
  if (!items.length) return null;
  const index = Math.max(0, Math.floor((items.length - 1) / 2));
  return { item: items[index], index };
}
function signalTierFromModelOdds(odds) {
  if (odds >= 1.45 && odds <= 1.75) return "quality";
  if (odds > 1.75 && odds <= 2.3) return "value";
  if (odds > 2.3 && odds <= 3.2) return "high_value";
  return null;
}
function passesTierQuality(params) {
  const { tier, probability, reliability, dataQuality } = params;
  if (!tier) return false;
  if (tier === "quality") {
    return probability >= 0.56 && reliability >= 68 && dataQuality >= 67;
  }
  if (tier === "value") {
    return probability >= 0.43 && reliability >= 72 && dataQuality >= 67;
  }
  return probability >= 0.31 && reliability >= 78 && dataQuality >= 100;
}
function playabilityUpliftCap(type, minute) {
  if (type === "corners") {
    if (minute < 45) return 3;
    if (minute < 60) return 2;
    if (minute < 75) return 1;
    return 1;
  }
  if (type === "shots") {
    if (minute < 45) return 6;
    if (minute < 60) return 4;
    if (minute < 75) return 2;
    return 1;
  }
  if (minute < 45) return 4;
  if (minute < 60) return 3;
  if (minute < 75) return 2;
  return 1;
}
function minimumPlayableProbability(type, minute) {
  if (type === "corners") return minute >= 75 ? 0.55 : 0.52;
  if (type === "shots") return minute >= 75 ? 0.54 : 0.5;
  return minute >= 75 ? 0.54 : 0.5;
}
function minimumPlayableHeadroom(type, minute) {
  if (type === "corners") return minute >= 75 ? 0.5 : 1;
  if (type === "shots") return minute >= 60 ? 1.5 : 2;
  return minute >= 60 ? 1.5 : 2;
}
function buildPlayabilityEnvelope(params) {
  const {
    type,
    minute,
    baseline,
    projectedFinal,
    reliability,
    dataQuality,
    candidates
  } = params;
  const upliftCap = playabilityUpliftCap(type, minute);
  const probabilityFloor = minimumPlayableProbability(type, minute);
  const minHeadroom = minimumPlayableHeadroom(type, minute);
  return candidates.filter((c) => {
    const threshold = Number(c?.threshold);
    const probability = safeNumber(c?.probability, 0);
    const tier = c?.signal_tier ?? null;
    const headroom = projectedFinal - threshold;
    if (!Number.isFinite(threshold)) return false;
    if (baseline != null && threshold < baseline - 1e-9) return false;
    if (baseline != null && threshold > baseline + upliftCap + 1e-9) return false;
    if (probability < probabilityFloor) return false;
    if (headroom < minHeadroom) return false;
    if (!passesTierQuality({ tier, probability, reliability, dataQuality })) return false;
    return true;
  }).map((c) => ({
    ...c,
    headroom: Number((projectedFinal - Number(c.threshold)).toFixed(2)),
    playable: true
  })).sort((a, b2) => Number(a.threshold) - Number(b2.threshold));
}
function selectMarketFacingCandidate(candidates) {
  if (!candidates.length) return null;
  const index = candidates.length - 1;
  return { item: candidates[index], index };
}
function getLineCandidates(params) {
  const {
    type,
    current,
    projected,
    heuristicProbability,
    reliability,
    minGap = 2
  } = params;
  const buffer2 = marketProjectionBuffer(type);
  const lines = LIVE_MARKET_LINES[type] || [];
  return lines.filter(
    (threshold) => current < threshold && threshold - current >= minGap && threshold <= projected + buffer2
  ).map((threshold) => {
    const probability = candidateProbability({
      current,
      threshold,
      projected,
      heuristicProbability,
      reliability
    });
    const modelFairOdds = estimatedModelOdds(probability);
    return {
      threshold,
      probability,
      model_fair_odds: modelFairOdds,
      signal_tier: signalTierFromModelOdds(modelFairOdds)
    };
  });
}
function predictionDataQuality(stats, type) {
  const completeness = statsCompleteness(stats);
  if (type === "corners") {
    return completeness.corners ? completeness.shots && completeness.shots_on_target ? 100 : 82 : 0;
  }
  if (type === "shots") {
    return completeness.shots ? completeness.shots_on_target ? 100 : 82 : 0;
  }
  return completeness.fouls ? completeness.corners || completeness.shots ? 100 : 82 : 0;
}
function buildLivePrediction(params) {
  const {
    type,
    predictionType,
    titleUnit,
    badge,
    color,
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability,
    reliability,
    reasons
  } = params;
  const dataQuality = predictionDataQuality(stats, type);
  const allCandidates = getLineCandidates({
    type,
    current,
    projected: projectedFinal,
    heuristicProbability,
    reliability,
    minGap: 2
  });
  const baseline = legacyBaselineThreshold(type, current, projectedFinal, 2);
  const historicalCap = historicalUpliftCap(type, minute);
  let candidates = allCandidates.filter((c) => Boolean(c.signal_tier));
  if (type === "shots" || type === "corners") {
    if (baseline == null) return null;
  }
  if (type === "corners" || type === "fouls") {
    candidates = candidates.filter((c) => c.signal_tier !== "high_value");
  }
  const playableCandidates = buildPlayabilityEnvelope({
    type,
    minute,
    baseline,
    projectedFinal,
    reliability,
    dataQuality,
    candidates
  });
  if (!playableCandidates.length) return null;
  const selected = selectMarketFacingCandidate(playableCandidates);
  if (!selected) return null;
  const chosen = selected.item;
  const tier = chosen.signal_tier;
  return {
    type: predictionType,
    title: `Over ${chosen.threshold} ${titleUnit}`,
    badge,
    color,
    probability: chosen.probability,
    message: `${current} ${titleUnit} actuellement`,
    threshold: chosen.threshold,
    current,
    signal_value: current,
    projected_value: projectedFinal,
    reliability,
    data_quality_score: dataQuality,
    model_fair_odds: chosen.model_fair_odds,
    signal_tier: tier,
    pricing_mode: "model_only",
    line_candidate_count: playableCandidates.length,
    line_candidate_rank: selected.index + 1,
    line_candidates: playableCandidates,
    baseline_threshold: baseline,
    historical_uplift_cap: historicalCap,
    selected_uplift: baseline != null ? Number((chosen.threshold - baseline).toFixed(2)) : null,
    model_version: LIVE_VALUE_MODEL_VERSION,
    minute,
    reasons: [
      ...reasons,
      `Projection finale ${projectedFinal}`,
      ...baseline != null ? [`Ligne de r\xE9f\xE9rence historique ${baseline}`] : [],
      ...historicalCap != null ? [`Plafond historique +${historicalCap}`] : [],
      `Zone jouable ${playableCandidates[0].threshold}-${playableCandidates[playableCandidates.length - 1].threshold}`,
      `Ligne march\xE9 ${selected.index + 1}/${playableCandidates.length}`,
      `Cote mod\xE8le ${chosen.model_fair_odds.toFixed(2)}`
    ]
  };
}
function computeHeatLevel(match) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const totals = getTotalStats(stats);
  let score = 0;
  score += totals.shots * 1.2;
  score += totals.shotsOnTarget * 2;
  score += totals.corners * 1.2;
  score += totals.fouls * 0.35;
  score += minute >= 55 ? 6 : 0;
  score += minute >= 70 ? 5 : 0;
  if (score >= 38) return "explosive";
  if (score >= 26) return "hot";
  if (score >= 14) return "warming";
  return "calm";
}
function predictTotalCorners(stats, minute, momentum) {
  if (!hasCompleteStatPair(stats, "corner_kicks")) return null;
  const totals = getTotalStats(stats);
  const current = totals.corners;
  if (minute < 18 || minute > 82) return null;
  if (current < 3) return null;
  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "corners",
    flow: flowData.flow
  });
  let probability = 0.58;
  let reliability = 52;
  const reasons = [];
  if (current >= 4) {
    probability += 0.06;
    reliability += 6;
    reasons.push(`${current} corners d\xE9j\xE0 obtenus`);
  }
  if (totals.shots >= 10) {
    probability += 0.06;
    reliability += 5;
    reasons.push(`${totals.shots} tirs cumul\xE9s`);
  }
  if (totals.shotsOnTarget >= 4) {
    probability += 0.04;
    reliability += 4;
    reasons.push(`${totals.shotsOnTarget} tirs cadr\xE9s`);
  }
  if (flowData.flow === "offensive") {
    probability += 0.07;
    reliability += 7;
    reasons.push(`Match offensif`);
  }
  if (flowData.flow === "defensive") {
    probability -= 0.08;
    reliability -= 8;
    reasons.push(`Rythme d\xE9fensif`);
  }
  if (minute >= 25 && minute <= 70) {
    probability += 0.05;
    reliability += 6;
    reasons.push(`Fen\xEAtre (${minute}')`);
  }
  probability = Math.min(0.9, Math.max(0.5, probability));
  reliability = Math.min(92, Math.max(40, reliability));
  if (reliability < 63) return null;
  if (minute >= 45 && minute < 60 && reliability < 78) return null;
  return buildLivePrediction({
    type: "corners",
    predictionType: "total_corners",
    titleUnit: "corners",
    badge: "Corners",
    color: "yellow",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons
  });
}
function predictTotalShots(stats, minute, momentum) {
  if (!hasCompleteStatPair(stats, "total_shots")) return null;
  const totals = getTotalStats(stats);
  const current = totals.shots;
  if (minute < 15 || minute > 83) return null;
  if (current < 6) return null;
  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({ current, minute, type: "shots", flow: flowData.flow });
  let probability = 0.6;
  let reliability = 55;
  const reasons = [];
  if (current >= 8) {
    probability += 0.06;
    reliability += 6;
    reasons.push(`${current} tirs d\xE9j\xE0 enregistr\xE9s`);
  }
  if (totals.shotsOnTarget >= 3) {
    probability += 0.06;
    reliability += 5;
    reasons.push(`${totals.shotsOnTarget} tirs cadr\xE9s`);
  }
  if (flowData.flow === "offensive") {
    probability += 0.08;
    reliability += 7;
    reasons.push(`Match offensif`);
  }
  if (flowData.flow === "defensive") {
    probability -= 0.1;
    reliability -= 8;
    reasons.push(`Rythme baisse`);
  }
  if (minute >= 20 && minute <= 72) {
    probability += 0.05;
    reliability += 5;
    reasons.push(`Minute (${minute}')`);
  }
  probability = Math.min(0.91, Math.max(0.5, probability));
  reliability = Math.min(93, Math.max(40, reliability));
  if (reliability < 64) return null;
  return buildLivePrediction({
    type: "shots",
    predictionType: "total_shots",
    titleUnit: "tirs",
    badge: "Tirs",
    color: "green",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons
  });
}
function predictTotalFouls(stats, minute, momentum) {
  if (!hasCompleteStatPair(stats, "fouls")) return null;
  const totals = getTotalStats(stats);
  const current = totals.fouls;
  if (minute < 18 || minute > 84) return null;
  if (current < 6) return null;
  const flowData = getMatchFlow(stats, minute, momentum);
  const projectedFinal = conservativeProjection({
    current,
    minute,
    type: "fouls",
    flow: flowData.flow === "offensive" ? "neutral" : flowData.flow
  });
  let probability = 0.57;
  let reliability = 54;
  const reasons = [];
  if (current >= 8) {
    probability += 0.05;
    reliability += 6;
    reasons.push(`${current} fautes d\xE9j\xE0 siffl\xE9es`);
  }
  if (minute >= 25 && minute <= 75) {
    probability += 0.05;
    reliability += 5;
    reasons.push(`P\xE9riode exploitable`);
  }
  if (flowData.flow === "defensive") {
    probability += 0.03;
    reliability += 3;
    reasons.push(`Match ferm\xE9`);
  }
  if (flowData.flow === "offensive") {
    probability -= 0.03;
    reliability -= 2;
  }
  probability = Math.min(0.88, Math.max(0.5, probability));
  reliability = Math.min(90, Math.max(40, reliability));
  if (reliability < 62) return null;
  return buildLivePrediction({
    type: "fouls",
    predictionType: "total_fouls",
    titleUnit: "fautes",
    badge: "Fautes",
    color: "orange",
    stats,
    minute,
    current,
    projectedFinal,
    heuristicProbability: probability,
    reliability,
    reasons
  });
}
function computeAiScore(match, predictions) {
  const best = predictions?.[0];
  if (!best) return 0;
  const momentum = computeMomentum(match?.live_stats || {});
  let score = 0;
  score += Math.round((best.probability || 0) * 50);
  score += Math.round((best.reliability || 0) * 0.35);
  score += Math.round((momentum.total || 0) * 0.2);
  return Math.min(99, score);
}
function computeValueScore(match, predictions) {
  const best = predictions?.[0];
  if (!best) return 0;
  const reliability = Math.min(100, Math.max(0, safeNumber(best.reliability, 0)));
  const dataQuality = Math.min(100, Math.max(0, safeNumber(best.data_quality_score, 0)));
  const probability = Math.min(1, Math.max(0, safeNumber(best.probability, 0)));
  const modelOdds = safeNumber(best.model_fair_odds, estimatedModelOdds(probability || 0.5));
  const bookmakerOdds = safeNumber(best.bookmaker_odds, 0);
  const implied = bookmakerOdds > 1 ? 1 / bookmakerOdds : null;
  const edge = implied != null ? probability - implied : null;
  const ev = bookmakerOdds > 1 ? probability * bookmakerOdds - 1 : null;
  let score = reliability * 0.35 + dataQuality * 0.3 + Math.min(25, Math.max(0, (modelOdds - 1.3) * 20));
  if (edge != null && ev != null) score = reliability * 0.25 + dataQuality * 0.2 + Math.max(0, Math.min(25, edge * 200)) + Math.max(0, Math.min(30, ev * 120));
  return Math.max(0, Math.min(99, Math.round(score)));
}
var espnStore = {
  async read(key) {
    const { data, error } = await supabase.from("espn_feed_cache").select("*").eq("cache_key", key).maybeSingle();
    if (error) throw error;
    return data;
  },
  async write(row) {
    const { error } = await supabase.from("espn_feed_cache").upsert(row, { onConflict: "cache_key" });
    if (error) throw error;
  },
  async reserve(bucket) {
    const { data, error } = await supabase.rpc("espn_take_request_slot", {
      p_bucket: bucket,
      p_max_calls: bucket === "summary" ? 8 : 30,
      p_window_seconds: 60
    });
    if (error) throw error;
    return data === true;
  },
  async blockFor(bucket, seconds) {
    const { error } = await supabase.rpc("espn_provider_backoff", {
      p_bucket: bucket,
      p_seconds: seconds
    });
    if (error) throw error;
  }
};
async function fetchEspnScoreboard(dateYYYYMMDD, _force = false) {
  const scoreboard = await fetchSharedEspnScoreboard(dateYYYYMMDD, espnStore);
  if (!scoreboard || !Array.isArray(scoreboard.events)) return scoreboard;
  return {
    ...scoreboard,
    events: scoreboard.events.map((event) => ({
      ...event,
      __espn_feed_fetched_at: scoreboard._feed_fetched_at || null
    }))
  };
}
function extractEspnMinute(status2) {
  const displayClock = status2?.displayClock || "";
  if (displayClock) {
    const found = String(displayClock).match(/(\d+)/);
    if (found) return safeNumber(found[1], 0);
  }
  const clock = status2?.clock;
  if (clock) return Math.floor(safeNumber(clock, 0) / 60);
  return 0;
}
function getEspnStatNullable(competitor, names) {
  const wanted = new Set(Array.isArray(names) ? names : [names]);
  const stats = competitor?.statistics || [];
  for (const s of stats) {
    if (wanted.has(String(s?.name || ""))) {
      return nullableNumber(s?.displayValue ?? s?.value);
    }
  }
  return null;
}
function countEspnCards(details, teamId) {
  let yellow = 0;
  let red = 0;
  for (const d of details || []) {
    const tid = String(d?.team?.id || "");
    if (!teamId || tid !== String(teamId)) continue;
    if (d?.yellowCard === true) yellow += 1;
    if (d?.redCard === true) red += 1;
  }
  return { yellow, red };
}
function normalizeEspnEventToOriginalMatch(event) {
  const competition = event?.competitions?.[0];
  if (!competition) return null;
  const status2 = competition?.status?.type?.state ? competition.status : event?.status || competition?.status || {};
  const statusType = status2?.type || {};
  const state2 = statusType?.state || "";
  const isLive = state2 === "in";
  const isFinished = Boolean(statusType?.completed);
  const competitors = competition?.competitors || [];
  const home = competitors.find((c) => c?.homeAway === "home");
  const away = competitors.find((c) => c?.homeAway === "away");
  if (!home || !away) return null;
  const homeTeam = home?.team || {};
  const awayTeam = away?.team || {};
  const leagueObj = event?.league || {};
  const seasonObj = event?.season || {};
  const details = competition?.details || [];
  const regionalLeague = String(event?.__espn_league_slug || "");
  const knownRegionalNames = {
    "crc.1": "Costa Rica Primera Division",
    "conmebol.sudamericana": "CONMEBOL Copa Sudamericana",
    "fifa.friendly.w": "International Friendly"
  };
  const leagueName = knownRegionalNames[regionalLeague] || leagueObj?.name || leagueObj?.abbreviation || seasonObj?.slug || "Football";
  const leagueId = regionalLeague || String(leagueObj?.id || leagueObj?.abbreviation || leagueName);
  const regionalWomen = regionalLeague === "fifa.friendly.w";
  const minute = extractEspnMinute(status2);
  const homeTeamId = String(homeTeam?.id || "");
  const awayTeamId = String(awayTeam?.id || "");
  const homeCorners = getEspnStatNullable(home, ["wonCorners", "corners"]);
  const awayCorners = getEspnStatNullable(away, ["wonCorners", "corners"]);
  const homeFouls = getEspnStatNullable(home, ["foulsCommitted", "fouls"]);
  const awayFouls = getEspnStatNullable(away, ["foulsCommitted", "fouls"]);
  const homeShots = getEspnStatNullable(home, ["totalShots", "shotsTotal"]);
  const awayShots = getEspnStatNullable(away, ["totalShots", "shotsTotal"]);
  const homeShotsOnTarget = getEspnStatNullable(home, ["shotsOnTarget", "shotsOnGoal"]);
  const awayShotsOnTarget = getEspnStatNullable(away, ["shotsOnTarget", "shotsOnGoal"]);
  const homePossession = getEspnStatNullable(home, ["possessionPct", "possession"]);
  const awayPossession = getEspnStatNullable(away, ["possessionPct", "possession"]);
  const homeCards = details.length ? countEspnCards(details, homeTeamId) : { yellow: null, red: null };
  const awayCards = details.length ? countEspnCards(details, awayTeamId) : { yellow: null, red: null };
  const liveStats = ensureLiveStatsShape({
    home: {
      corner_kicks: homeCorners,
      fouls: homeFouls,
      total_shots: homeShots,
      shots_on_target: homeShotsOnTarget,
      ball_possession: homePossession,
      yellow_cards: homeCards.yellow,
      red_cards: homeCards.red
    },
    away: {
      corner_kicks: awayCorners,
      fouls: awayFouls,
      total_shots: awayShots,
      shots_on_target: awayShotsOnTarget,
      ball_possession: awayPossession,
      yellow_cards: awayCards.yellow,
      red_cards: awayCards.red
    }
  });
  const homeLogo = homeTeam?.logo || homeTeam?.logos?.[0]?.href || null;
  const awayLogo = awayTeam?.logo || awayTeam?.logos?.[0]?.href || null;
  const leagueLogo = leagueObj?.logos?.[0]?.href || leagueObj?.logo || null;
  const eventDate = safeEspnDate(event?.date);
  if (!eventDate) return null;
  const eventId = String(event?.id || "");
  if (!eventId) return null;
  return {
    id: `espn:${eventId}`,
    source_match_id: eventId,
    source_name: "espn",
    home_team: regionalWomen ? String(homeTeam?.displayName || homeTeam?.name || "Home") + " Women" : homeTeam?.displayName || homeTeam?.name || "Home",
    away_team: regionalWomen ? String(awayTeam?.displayName || awayTeam?.name || "Away") + " Women" : awayTeam?.displayName || awayTeam?.name || "Away",
    home_score: safeNumber(home?.score, 0),
    away_score: safeNumber(away?.score, 0),
    current_minute: minute,
    league_name: leagueName,
    league: { name: leagueName, id: leagueId, api_id: leagueId },
    status: statusType?.name || statusType?.detail || state2 || "",
    is_live: isLive,
    is_finished: isFinished,
    event_date: eventDate,
    home_team_id: homeTeamId || null,
    away_team_id: awayTeamId || null,
    league_id: leagueId || null,
    home_logo: homeLogo,
    away_logo: awayLogo,
    league_logo: leagueLogo,
    live_stats: liveStats,
    stats_last_updated_at: statsCompleteness(liveStats).core_complete > 0 ? safeEspnDate(event?.__espn_feed_fetched_at) || null : null,
    raw_data: {
      source: "espn",
      event_id: eventId,
      espn_league_slug: regionalLeague || null,
      state: state2,
      display_clock: status2?.displayClock || "",
      status_detail: statusType?.detail || statusType?.description || "",
      home_team_obj: { api_id: homeTeamId, id: homeTeamId, logo: homeLogo },
      away_team_obj: { api_id: awayTeamId, id: awayTeamId, logo: awayLogo },
      league: { name: leagueName, api_id: leagueId, id: leagueId, logo: leagueLogo },
      live_stats: liveStats
    }
  };
}
async function fetchEspnLiveMatchesForMerge() {
  if (!ENABLE_ESPN_MERGE) return { matches: [], error: null };
  const days = espnLiveScoreboardDates();
  const feeds = await Promise.allSettled(days.map((day) => fetchEspnScoreboard(day, false)));
  const events = [];
  const errors = [];
  for (let i = 0; i < feeds.length; i++) {
    const feed = feeds[i];
    if (feed.status === "fulfilled") {
      events.push(...feed.value?.events || []);
    } else {
      errors.push(days[i] + ":" + String(feed.reason?.message || "ESPN unavailable"));
    }
  }
  const byEvent = /* @__PURE__ */ new Map();
  for (const event of events) {
    const id = String(event?.id || "");
    if (id && !byEvent.has(id)) byEvent.set(id, event);
  }
  return {
    matches: [...byEvent.values()].map(normalizeEspnEventToOriginalMatch).filter(Boolean).filter((m) => m.is_live && !m.is_finished),
    error: errors.length ? errors.join("; ") : null
  };
}
function regionalEspnLeaguesForFreeMatches(matches) {
  const found = /* @__PURE__ */ new Set();
  for (const match of matches || []) {
    if (!match?.is_live || match?.is_finished) continue;
    const league = String(getLeagueName(match) || "").toLowerCase();
    const home = String(match?.home_team || "").toLowerCase();
    const away = String(match?.away_team || "").toLowerCase();
    if (/costa rica|liga fpd|primera.*costa/.test(league)) found.add("crc.1");
    if (/sudamericana/.test(league)) found.add("conmebol.sudamericana");
    if (/friendly|amical/.test(league) && /women/.test(home) && /women/.test(away)) found.add("fifa.friendly.w");
  }
  return [...found].slice(0, 3);
}
async function fetchRegionalEspnLiveMatchesForMerge(matches) {
  const leagues = regionalEspnLeaguesForFreeMatches(matches);
  if (!ENABLE_ESPN_MERGE || !leagues.length) return { matches: [], calls: 0, leagues: [], errors: [] };
  const dates = espnLiveScoreboardDates();
  const jobs = leagues.flatMap((league) => dates.map((day) => ({ league, day })));
  const results = await Promise.allSettled(jobs.map((job) => fetchSharedEspnRegionalScoreboard(job.day, job.league, espnStore)));
  const events = /* @__PURE__ */ new Map();
  const errors = [];
  for (let i = 0; i < results.length; i++) {
    const result = results[i], job = jobs[i];
    if (result.status === "rejected") {
      errors.push(job.league + ":" + job.day + ":unavailable");
      continue;
    }
    for (const event of result.value?.events || []) {
      if (!event?.id) continue;
      const key = String(event.id);
      const decorated = {
        ...event,
        __espn_feed_fetched_at: result.value?._feed_fetched_at || null,
        __espn_league_slug: job.league
      };
      if (!events.has(key)) events.set(key, decorated);
    }
  }
  return {
    matches: [...events.values()].map(normalizeEspnEventToOriginalMatch).filter(Boolean).filter((m) => m.is_live && !m.is_finished),
    calls: jobs.length,
    leagues,
    errors
  };
}
function liveStatsAgreementScore(primaryStats, secondaryStats, minuteGap) {
  if (minuteGap > 2) return null;
  const a = ensureLiveStatsShape(primaryStats || {});
  const b2 = ensureLiveStatsShape(secondaryStats || {});
  const configs = [
    { key: "corner_kicks", tolerance: 1 },
    { key: "total_shots", tolerance: 2 },
    { key: "shots_on_target", tolerance: 1 },
    { key: "fouls", tolerance: 2 }
  ];
  const scores = [];
  for (const cfg of configs) {
    const ah = nullableNumber(a?.home?.[cfg.key]);
    const aa = nullableNumber(a?.away?.[cfg.key]);
    const bh = nullableNumber(b2?.home?.[cfg.key]);
    const ba = nullableNumber(b2?.away?.[cfg.key]);
    if (ah == null || aa == null || bh == null || ba == null) continue;
    const diff = Math.abs(ah + aa - (bh + ba));
    const excess = Math.max(0, diff - cfg.tolerance);
    scores.push(Math.max(0, 100 - excess * 20));
  }
  if (!scores.length) return null;
  return Math.round(scores.reduce((sum, x) => sum + x, 0) / scores.length);
}
function mergeOneOriginalWithEspn(original, espn) {
  const originalStats = getMatchLiveStats(original);
  const espnStats = getMatchLiveStats(espn);
  const mergedStats = preferObservedCoreMarketPairs(
    espnStats,
    mergeLiveStats(originalStats, espnStats)
  );
  const originalMinute = safeNumber(original?.current_minute ?? original?.minute, 0);
  const espnMinute = safeNumber(espn?.current_minute ?? espn?.minute, 0);
  const statsAgreementScore = liveStatsAgreementScore(originalStats, espnStats, Math.abs(originalMinute - espnMinute));
  const merged = {
    ...original,
    current_minute: espnMinute > 0 ? espnMinute : originalMinute,
    home_score: nullableNumber(espn?.home_score) ?? original?.home_score,
    away_score: nullableNumber(espn?.away_score) ?? original?.away_score,
    live_stats: mergedStats,
    stats_last_updated_at: espn?.stats_last_updated_at || original?.stats_last_updated_at || null,
    home_logo: original?.home_logo || espn?.home_logo || original?.raw_data?.home_logo || espn?.raw_data?.home_logo || null,
    away_logo: original?.away_logo || espn?.away_logo || original?.raw_data?.away_logo || espn?.raw_data?.away_logo || null,
    league_logo: original?.league_logo || espn?.league_logo || original?.raw_data?.league_logo || espn?.raw_data?.league_logo || null
  };
  merged.raw_data = {
    ...original?.raw_data || {},
    source: "merged",
    merge_meta: {
      canonical_match_id: buildCanonicalMatchId(original),
      sources: ["api_original", "espn"],
      confidence_score: Math.round(sameMatchScore(original, espn) * 100),
      stats_agreement_score: statsAgreementScore,
      espn_match_id: espn?.source_match_id || espn?.id || null,
      primary_source: "espn",
      merged_at: nowIso()
    },
    espn_primary_stats: ensureLiveStatsShape(espnStats),
    live_stats: mergedStats,
    home_logo: merged.home_logo,
    away_logo: merged.away_logo,
    league_logo: merged.league_logo,
    home_team_obj: {
      ...original?.raw_data?.home_team_obj || {},
      logo: merged.home_logo,
      espn_id: espn?.home_team_id || espn?.raw_data?.home_team_obj?.id || null
    },
    away_team_obj: {
      ...original?.raw_data?.away_team_obj || {},
      logo: merged.away_logo,
      espn_id: espn?.away_team_id || espn?.raw_data?.away_team_obj?.id || null
    },
    league: {
      ...original?.raw_data?.league || original?.league || {},
      name: getLeagueName(original),
      logo: merged.league_logo,
      espn_id: espn?.league_id || espn?.raw_data?.league?.id || null
    }
  };
  return merged;
}
function prepareEspnOnlyMatch(espn) {
  const liveStats = ensureLiveStatsShape(getMatchLiveStats(espn));
  return {
    ...espn,
    live_stats: liveStats,
    raw_data: {
      ...espn?.raw_data || {},
      source: "merged",
      merge_meta: {
        canonical_match_id: buildCanonicalMatchId(espn),
        sources: ["espn"],
        confidence_score: 80,
        espn_match_id: espn?.source_match_id || espn?.id || null,
        primary_source: "espn",
        merged_at: nowIso()
      },
      espn_primary_stats: liveStats,
      live_stats: liveStats,
      home_logo: espn?.home_logo || espn?.raw_data?.home_logo || null,
      away_logo: espn?.away_logo || espn?.raw_data?.away_logo || null,
      league_logo: espn?.league_logo || espn?.raw_data?.league_logo || null
    }
  };
}
function mergeOriginalAndEspnMatches(originalMatches, espnMatches, knownMappings = /* @__PURE__ */ new Map()) {
  const sourceRows = [];
  const providerMappings = [];
  const entries = [];
  for (const original of originalMatches || []) {
    const key = buildCanonicalMatchId(original);
    const match = {
      ...original,
      raw_data: {
        ...original?.raw_data || {},
        // Immutable BSD observations from /events/live/; other providers are
        // supplementary, not replacements for fully known BSD market pairs.
        bsd_primary_stats: ensureLiveStatsShape(getMatchLiveStats(original)),
        merge_meta: {
          canonical_match_id: key,
          sources: ["api_original"],
          confidence_score: 70,
          primary_source: "api_original",
          merged_at: nowIso()
        }
      }
    };
    entries.push({ key, match, source: "api_original" });
    sourceRows.push(sourceRowFromMatch(original, "api_original"));
  }
  let duplicatesMerged = 0;
  let espnOnly = 0;
  for (const espn of espnMatches || []) {
    sourceRows.push(sourceRowFromMatch(espn, "espn"));
    const espnId = String(espn?.source_match_id || espn?.raw_data?.event_id || "");
    let bestIndex = -1;
    let bestScore = 0;
    const knownPrimaryId = knownMappings.get(espnId);
    if (knownPrimaryId) {
      const mappedIndex = entries.findIndex(
        (entry) => String(entry.match?.id || "") === knownPrimaryId && entry.source !== "espn" && sameMatchScore(entry.match, espn) >= 0.72
      );
      if (mappedIndex >= 0) {
        bestIndex = mappedIndex;
        bestScore = 1;
      }
    }
    if (bestIndex < 0) {
      for (let i = 0; i < entries.length; i++) {
        if (entries[i].source === "espn") continue;
        const score = sameMatchScore(entries[i].match, espn);
        if (score > bestScore) {
          bestScore = score;
          bestIndex = i;
        }
      }
    }
    if (bestIndex >= 0 && bestScore >= 0.72) {
      if (espnId && bestScore >= 0.85) {
        const date2 = safeEspnDate(getMatchEventDate(espn));
        providerMappings.push({
          espn_id: espnId,
          primary_match_id: String(entries[bestIndex].match?.id || ""),
          fixture_date: date2 ? date2.slice(0, 10) : null,
          confidence: Math.min(1, bestScore),
          mapped_at: nowIso()
        });
      }
      entries[bestIndex].match = mergeOneOriginalWithEspn(entries[bestIndex].match, espn);
      entries[bestIndex].source = "merged";
      duplicatesMerged++;
    } else {
      const key = buildCanonicalMatchId(espn);
      entries.push({ key, match: prepareEspnOnlyMatch(espn), source: "espn" });
      espnOnly++;
    }
  }
  const mergedMatches = entries.map((e) => e.match);
  return {
    mergedMatches,
    sourceRows,
    providerMappings,
    meta: {
      original_source_matches: originalMatches.length,
      espn_source_matches: espnMatches.length,
      merged_matches: mergedMatches.length,
      duplicates_merged: duplicatesMerged,
      espn_only_matches: espnOnly,
      espn_enabled: ENABLE_ESPN_MERGE
    }
  };
}
function mergeAdditionalProviderMatches(baseMatches, providerMatches, providerName) {
  const out = [...baseMatches || []];
  const sourceRows = [];
  let merged = 0;
  let providerOnly = 0;
  const quality = safeNumber(FREE_SOURCE_QUALITY?.[providerName]?.overall, 60);
  for (const provider of providerMatches || []) {
    sourceRows.push(sourceRowFromMatch(provider, providerName));
    let bestIndex = -1;
    let bestScore = 0;
    for (let i = 0; i < out.length; i++) {
      const score = sameMatchScore(out[i], provider);
      if (score > bestScore) {
        bestScore = score;
        bestIndex = i;
      }
    }
    if (bestIndex >= 0 && bestScore >= 0.72) {
      const current = out[bestIndex];
      const currentStats = getMatchLiveStats(current);
      const providerStats = getMatchLiveStats(provider);
      const currentMinute = safeNumber(current?.current_minute ?? current?.minute, 0);
      const providerMinute = safeNumber(provider?.current_minute ?? provider?.minute, 0);
      const refs = {
        ...current?.raw_data?.provider_refs || {},
        [providerName]: {
          id: String(provider?.source_match_id || provider?.id || ""),
          slug: String(provider?.raw_data?.sportscore_slug || ""),
          quality
        }
      };
      const sources = [
        .../* @__PURE__ */ new Set([
          ...current?.raw_data?.merge_meta?.sources || [],
          providerName
        ])
      ];
      const bsdPrimary = current?.raw_data?.merge_meta?.primary_source === "api_original";
      const espnPrimary = current?.raw_data?.merge_meta?.primary_source === "espn";
      const providerIsFresher = !bsdPrimary && !espnPrimary && providerMinute >= currentMinute && Boolean(provider?.is_live || provider?.is_finished);
      out[bestIndex] = {
        ...current,
        current_minute: bsdPrimary && currentMinute > 0 ? currentMinute : Math.max(currentMinute, providerMinute),
        home_score: current?.home_score == null || providerIsFresher ? provider?.home_score ?? current?.home_score : current?.home_score,
        away_score: current?.away_score == null || providerIsFresher ? provider?.away_score ?? current?.away_score : current?.away_score,
        home_logo: current?.home_logo || provider?.home_logo || null,
        away_logo: current?.away_logo || provider?.away_logo || null,
        live_stats: mergeLiveStats(currentStats, providerStats),
        stats_last_updated_at: provider?.stats_last_updated_at || current?.stats_last_updated_at || null,
        raw_data: {
          ...current?.raw_data || {},
          provider_refs: refs,
          merge_meta: {
            ...current?.raw_data?.merge_meta || {},
            canonical_match_id: current?.raw_data?.merge_meta?.canonical_match_id || buildCanonicalMatchId(current),
            sources,
            confidence_score: Math.max(
              safeNumber(current?.raw_data?.merge_meta?.confidence_score, 0),
              Math.round(bestScore * 100),
              Math.min(95, quality)
            ),
            primary_source: current?.raw_data?.merge_meta?.primary_source || "api_original",
            merged_at: nowIso()
          }
        }
      };
      merged++;
    } else if (provider?.is_live === true) {
      const stats = ensureLiveStatsShape(getMatchLiveStats(provider));
      out.push({
        ...provider,
        live_stats: stats,
        raw_data: {
          ...provider?.raw_data || {},
          provider_refs: {
            [providerName]: {
              id: String(provider?.source_match_id || provider?.id || ""),
              slug: String(provider?.raw_data?.sportscore_slug || ""),
              quality
            }
          },
          merge_meta: {
            canonical_match_id: buildCanonicalMatchId(provider),
            sources: [providerName],
            confidence_score: Math.min(90, quality),
            primary_source: providerName,
            merged_at: nowIso()
          },
          live_stats: stats
        }
      });
      providerOnly++;
    }
  }
  return { matches: out, sourceRows, merged, providerOnly };
}
async function enrichLiveMatchesWithEspnSummaries(matches) {
  const out = [...matches || []];
  const maxCalls = Math.max(0, Math.min(4, safeEnvInt("ESPN_SUMMARY_STATS_MAX_CALLS_PER_REFRESH", 2)));
  let calls = 0, enriched = 0, completePairsGained = 0;
  const eligible = out.map((m, index) => ({ m, index })).filter(({ m }) => {
    const minute = safeNumber(m?.current_minute ?? m?.minute, 0);
    if (!m?.is_live || m?.is_finished || minute < 8 || minute > 90) return false;
    if (statsCompleteness(getMatchLiveStats(m)).core_complete >= 3) return false;
    const raw = m?.raw_data || {}, refs = raw?.provider_refs || {};
    const eventId = String(raw?.merge_meta?.espn_match_id || raw?.event_id || refs?.espn?.id || (String(m?.id || "").startsWith("espn:") ? m.id : "")).replace(/^espn:/, "");
    const homeId = String(raw?.home_team_obj?.espn_id || raw?.home_team_obj?.id || "");
    const awayId = String(raw?.away_team_obj?.espn_id || raw?.away_team_obj?.id || "");
    return /^\d+$/.test(eventId) && !!homeId && !!awayId && homeId !== awayId;
  }).sort(
    (a, b2) => statsCompleteness(getMatchLiveStats(a.m)).core_complete - statsCompleteness(getMatchLiveStats(b2.m)).core_complete
  );
  for (const { m, index } of eligible.slice(0, maxCalls)) {
    const raw = m.raw_data || {};
    const eventId = String(raw?.merge_meta?.espn_match_id || raw?.event_id || raw?.provider_refs?.espn?.id || (String(m.id || "").startsWith("espn:") ? m.id : "")).replace(/^espn:/, "");
    const homeId = String(raw?.home_team_obj?.espn_id || raw?.home_team_obj?.id || "");
    const awayId = String(raw?.away_team_obj?.espn_id || raw?.away_team_obj?.id || "");
    try {
      calls++;
      const summary = await fetchSharedEspnSummary(eventId, espnStore);
      const observed = normalizeEspnSummaryStats(summary, homeId, awayId);
      if (!observed) continue;
      const hasRealStats = ["home", "away"].some((side) => Object.values(observed[side] || {}).some((v) => nullableNumber(v) != null));
      if (!hasRealStats) continue;
      const before = statsCompleteness(getMatchLiveStats(m)).core_complete;
      const merged = mergeLiveStats(getMatchLiveStats(m), observed);
      const after = statsCompleteness(merged).core_complete;
      completePairsGained += Math.max(0, after - before);
      out[index] = {
        ...m,
        live_stats: merged,
        stats_last_updated_at: nowIso(),
        raw_data: {
          ...raw,
          live_stats: merged,
          espn_summary_observed_stats: observed,
          espn_primary_stats: mergeLiveStats(raw.espn_primary_stats || {}, observed, true),
          espn_summary_event_id: eventId,
          stats_sources: [
            .../* @__PURE__ */ new Set([...raw.stats_sources || [], "espn_summary"])
          ]
        }
      };
      enriched++;
    } catch (e) {
      console.warn("ESPN summary stats unavailable", eventId, e);
    }
  }
  return { matches: out, calls, enriched, complete_pairs_gained: completePairsGained };
}
async function enrichLiveMatchesWithMoviOddsStats(matches) {
  const result = {
    matches: [...matches || []],
    sourceRows: [],
    observations: 0,
    enriched: 0
  };
  if ((Deno.env.get("LIVE_MOVIODDS_STATS_ENABLED") || "1") === "0") return result;
  const inputs = result.matches.filter((m) => m?.is_live === true && !m?.is_finished && statsCompleteness(getMatchLiveStats(m)).core_complete < 3).map((m) => ({
    match_id: String(m?.id || ""),
    home: String(m?.home_team?.name ?? m?.home_team ?? ""),
    away: String(m?.away_team?.name ?? m?.away_team ?? ""),
    kickoff: String(getMatchEventDate(m) || "")
  })).filter((m) => m.match_id && m.home && m.away && Number.isFinite(Date.parse(m.kickoff))).slice(0, 100);
  if (!inputs.length) return result;
  try {
    const observed = await fetchVerifiedMoviOddsLiveStats(inputs, supabase);
    const index = new Map(result.matches.map((m, i) => [String(m?.id), i]));
    for (const item of observed) {
      const i = index.get(item.match_id);
      if (typeof i !== "number") continue;
      const before = result.matches[i];
      const baseline = ensureLiveStatsShape(getMatchLiveStats(before));
      const fillOnly = { home: {}, away: {} };
      for (const key of [
        "corner_kicks",
        "total_shots",
        "shots_on_target",
        "shots_off_target",
        "attacks",
        "dangerous_attacks",
        "yellow_cards",
        "red_cards"
      ]) {
        if (hasCompleteStatPair(baseline, key)) continue;
        const h = nullableNumber(item.stats?.home?.[key]);
        const a = nullableNumber(item.stats?.away?.[key]);
        if (h !== null && a !== null) {
          fillOnly.home[key] = h;
          fillOnly.away[key] = a;
        }
      }
      for (const side of ["home", "away"]) {
        if (nullableNumber(baseline?.[side]?.ball_possession) == null) {
          const p = nullableNumber(item.stats?.[side]?.ball_possession);
          if (p !== null) fillOnly[side].ball_possession = p;
        }
      }
      const merged = mergeLiveStats(baseline, fillOnly, false);
      result.observations++;
      result.sourceRows.push({
        ...sourceRowFromMatch({
          ...before,
          live_stats: item.stats,
          raw_data: {
            ...before?.raw_data || {},
            live_stats: item.stats,
            provider_refs: {
              ...before?.raw_data?.provider_refs || {},
              moviodds: { id: item.provider_id }
            },
            stats_authority: "moviodds_live_stats"
          }
        }, "moviodds"),
        source_match_id: item.provider_id
      });
      if (JSON.stringify(merged) === JSON.stringify(baseline)) continue;
      result.matches[i] = {
        ...before,
        live_stats: merged,
        stats_last_updated_at: nowIso(),
        raw_data: {
          ...before?.raw_data || {},
          live_stats: merged,
          moviodds_observed_stats: item.stats,
          stats_sources: [.../* @__PURE__ */ new Set([
            ...before?.raw_data?.stats_sources || [],
            "moviodds_live_stats"
          ])]
        }
      };
      result.enriched++;
    }
  } catch (e) {
    console.warn("MOVIODDS_LIVE_STATS_UNAVAILABLE", e?.message || String(e));
  }
  return result;
}
async function enrichLiveMatchesWithFreeStats(matches) {
  const out = [...matches || []];
  let sportscoreCalls = 0;
  let thesportsdbCalls = 0;
  let thesportsdbResolveCalls = 0;
  let enriched = 0;
  let oddsSectionsDetected = 0;
  const maxSportScore = Math.max(
    0,
    Math.min(8, safeEnvInt("SPORTSCORE_STATS_MAX_CALLS_PER_REFRESH", 4))
  );
  const maxTsdb = Math.max(
    0,
    Math.min(5, safeEnvInt("THESPORTSDB_STATS_MAX_CALLS_PER_REFRESH", 2))
  );
  const maxTsdbResolve = Math.max(
    0,
    Math.min(3, safeEnvInt("THESPORTSDB_RESOLVE_MAX_CALLS_PER_REFRESH", 2))
  );
  const candidates = out.map((m, index) => ({ m, index })).filter(({ m }) => {
    const minute = safeNumber(m?.current_minute ?? m?.minute, 0);
    if (minute > 90 || minute > 0 && minute < 5 || m?.is_finished) return false;
    if (m?.is_live === false) return false;
    return statsCompleteness(getMatchLiveStats(m)).core_complete < 3;
  }).sort(
    (a, b2) => statsCompleteness(getMatchLiveStats(a.m)).core_complete - statsCompleteness(getMatchLiveStats(b2.m)).core_complete
  );
  const sportRotation = candidates.length ? Math.floor(Date.now() / 6e4) * Math.max(1, maxSportScore) % candidates.length : 0;
  const rotatedCandidates = [...candidates.slice(sportRotation), ...candidates.slice(0, sportRotation)];
  for (const { m, index } of rotatedCandidates) {
    let current = out[index];
    let before = statsCompleteness(getMatchLiveStats(current)).core_complete;
    const refs = current?.raw_data?.provider_refs || {};
    const sportDetailLastAttempt = Date.parse(String(current?.raw_data?.sportscore_detail_last_attempt_at || ""));
    const sportDetailDue = !Number.isFinite(sportDetailLastAttempt) || Date.now() - sportDetailLastAttempt >= SPORTSCORE_STATS_REFRESH_SECONDS * 1e3;
    let thesportsdbRefId = refs?.thesportsdb?.id ? String(refs.thesportsdb.id).replace(/^thesportsdb:/, "") : "";
    if (before < 3 && sportscoreCalls < maxSportScore && sportDetailDue && refs?.sportscore?.slug) {
      try {
        sportscoreCalls++;
        current = { ...current, raw_data: { ...current.raw_data || {}, sportscore_detail_last_attempt_at: nowIso() } };
        const payload = await fetchSportScoreDetail(String(refs.sportscore.slug));
        const detail = normalizeSportScoreDetail(payload);
        const detailMinute = nullableNumber(detail?.minute);
        if (detailMinute != null && detailMinute > 0 && detailMinute <= 130) {
          current = {
            ...current,
            current_minute: Math.max(safeNumber(current?.current_minute, 0), detailMinute),
            raw_data: {
              ...current?.raw_data || {},
              sportscore_minute_source: "detail",
              sportscore_minute_raw: String(payload?.match?.live_minute ?? "")
            }
          };
        }
        if (detail?.odds_probe?.available) oddsSectionsDetected++;
        const observedStats = detail?.stats || {};
        const hasObservedStats = ["home", "away"].some(
          (side) => Object.values(observedStats?.[side] || {}).some((v) => nullableNumber(v) != null)
        );
        if (hasObservedStats) {
          current = {
            ...current,
            raw_data: {
              ...current?.raw_data || {},
              sportscore_detail_observed_stats: observedStats
            }
          };
        }
        const baselineStats = ensureLiveStatsShape(getMatchLiveStats(current));
        const mergedStats = mergeLiveStats(
          baselineStats,
          detail?.stats || {},
          true
        );
        const after = statsCompleteness(mergedStats).core_complete;
        const partialStatsUpdated = JSON.stringify(mergedStats) !== JSON.stringify(baselineStats);
        if (after > before || partialStatsUpdated) {
          current = {
            ...current,
            live_stats: mergedStats,
            stats_last_updated_at: nowIso(),
            raw_data: {
              ...current?.raw_data || {},
              live_stats: mergedStats,
              // Preserve only observations received directly from SportScore:
              // do not attribute stats coming from ESPN/BSD to this provider.
              sportscore_detail_observed_stats: detail?.stats || {},
              sportscore_detail: {
                has_lineups: Boolean(detail?.lineups),
                timeline_count: Array.isArray(detail?.timeline) ? detail.timeline.length : 0,
                odds_probe: detail?.odds_probe || null
              },
              stats_sources: [
                .../* @__PURE__ */ new Set([
                  ...current?.raw_data?.stats_sources || [],
                  "sportscore_stats"
                ])
              ],
              stats_authority: "sportscore_stats"
            }
          };
          before = after;
          enriched++;
        } else if (detail?.odds_probe?.available) {
          current = {
            ...current,
            raw_data: {
              ...current?.raw_data || {},
              sportscore_detail: {
                ...current?.raw_data?.sportscore_detail || {},
                odds_probe: detail.odds_probe
              }
            }
          };
        }
      } catch (e) {
        console.warn("SportScore detail unavailable", refs?.sportscore?.slug, e);
      }
    }
    if (before < 3 && !/^\d+$/.test(thesportsdbRefId) && thesportsdbResolveCalls < maxTsdbResolve) {
      try {
        const eventKickoff = safeEspnDate(getMatchEventDate(current)) || void 0;
        const home = String(current?.home_team?.name ?? current?.home_team ?? "");
        const away = String(current?.away_team?.name ?? current?.away_team ?? "");
        if (home && away) {
          thesportsdbResolveCalls++;
          const resolvedId = await resolveTheSportsDbEvent(home, away, eventKickoff);
          if (resolvedId && /^\d+$/.test(resolvedId)) {
            thesportsdbRefId = resolvedId;
            current = {
              ...current,
              raw_data: {
                ...current?.raw_data || {},
                provider_refs: {
                  ...current?.raw_data?.provider_refs || {},
                  thesportsdb: {
                    id: resolvedId,
                    quality: safeNumber(FREE_SOURCE_QUALITY?.thesportsdb?.overall, 79),
                    resolved: true
                  }
                }
              }
            };
          }
        }
      } catch (e) {
        console.warn("TheSportsDB event resolution unavailable", current?.id, e);
      }
    }
    if (before < 3 && thesportsdbCalls < maxTsdb && /^\d+$/.test(thesportsdbRefId)) {
      try {
        thesportsdbCalls++;
        const detail = await fetchTheSportsDbStats(thesportsdbRefId);
        const mergedStats = mergeLiveStats(
          getMatchLiveStats(current),
          detail?.stats || {},
          true
        );
        const after = statsCompleteness(mergedStats).core_complete;
        if (after > before) {
          current = {
            ...current,
            live_stats: mergedStats,
            stats_last_updated_at: nowIso(),
            raw_data: {
              ...current?.raw_data || {},
              live_stats: mergedStats,
              stats_sources: [
                .../* @__PURE__ */ new Set([
                  ...current?.raw_data?.stats_sources || [],
                  "thesportsdb_stats"
                ])
              ],
              stats_authority: "thesportsdb_stats"
            }
          };
          before = after;
          enriched++;
        }
      } catch (e) {
        console.warn("TheSportsDB stats unavailable", thesportsdbRefId, e);
      }
    }
    out[index] = current;
  }
  return {
    matches: out,
    calls: sportscoreCalls + thesportsdbResolveCalls + thesportsdbCalls,
    sportscore_calls: sportscoreCalls,
    thesportsdb_resolve_calls: thesportsdbResolveCalls,
    thesportsdb_calls: thesportsdbCalls,
    enriched,
    odds_sections_detected: oddsSectionsDetected
  };
}
function applyPredictionQualityContext(match, pred) {
  if (!pred) return pred;
  const mergeMeta = match?.raw_data?.merge_meta || {};
  const sourceNames = /* @__PURE__ */ new Set([
    ...Array.isArray(mergeMeta?.sources) ? mergeMeta.sources : [],
    ...Array.isArray(match?.raw_data?.stats_sources) ? match.raw_data.stats_sources : []
  ]);
  const sourceCount = sourceNames.size || 1;
  const sourceConfidence = Math.min(100, Math.max(0, safeNumber(mergeMeta?.confidence_score, sourceCount >= 2 ? 75 : 65)));
  const sourceAgreementRaw = nullableNumber(mergeMeta?.stats_agreement_score);
  const sourceAgreement = sourceAgreementRaw == null ? null : Math.min(100, Math.max(0, sourceAgreementRaw));
  const age = statsAgeSeconds(match);
  const freshness = Number.isFinite(age) ? age : null;
  let reliability = safeNumber(pred.reliability, 0);
  let dataQuality = safeNumber(pred.data_quality_score, 0);
  if (sourceCount >= 2 && sourceConfidence >= 72) {
    reliability += Math.min(4, (sourceConfidence - 70) * 0.1);
    dataQuality += 4;
    if (sourceAgreement != null && sourceAgreement >= 80) {
      reliability += 4;
      dataQuality += 4;
    } else if (sourceAgreement != null && sourceAgreement < 60) {
      reliability -= 10;
      dataQuality -= 12;
    }
  } else if (sourceConfidence < 60) {
    reliability -= 6;
    dataQuality -= 8;
  }
  if (freshness != null && freshness > 180) {
    reliability -= freshness > 300 ? 12 : 8;
    dataQuality -= freshness > 300 ? 15 : 10;
  }
  reliability = Math.min(98, Math.max(35, reliability));
  dataQuality = Math.min(100, Math.max(0, dataQuality));
  const tier = pred.signal_tier;
  const qualityOk = passesTierQuality({ tier, probability: safeNumber(pred.probability, 0), reliability, dataQuality });
  return {
    ...pred,
    reliability: Number(reliability.toFixed(1)),
    data_quality_score: Number(dataQuality.toFixed(1)),
    freshness_seconds: freshness,
    source_count: sourceCount,
    source_confidence: sourceConfidence,
    source_agreement_score: sourceAgreement,
    signal_tier: qualityOk ? tier : null,
    value_score: 0
  };
}
function normalizeMatch(match, updatedAt) {
  const stats = match?.live_stats || {};
  const minute = safeNumber(match?.current_minute, 0);
  const momentum = computeMomentum(stats);
  const allPredictions = [
    predictTotalShots(stats, minute, momentum),
    predictTotalCorners(stats, minute, momentum),
    predictTotalFouls(stats, minute, momentum)
  ].filter(Boolean).map((p) => applyPredictionQualityContext(match, p)).map((p) => ({ ...p, value_score: computeValueScore(match, [p]) }));
  allPredictions.sort((a, b2) => {
    const av = safeNumber(a?.value_score, 0);
    const bv = safeNumber(b2?.value_score, 0);
    if (bv !== av) return bv - av;
    if ((b2.reliability || 0) !== (a.reliability || 0)) return (b2.reliability || 0) - (a.reliability || 0);
    return (b2.probability || 0) - (a.probability || 0);
  });
  const predictions = allPredictions.filter((p) => Boolean(p?.signal_tier));
  return {
    ...match,
    momentum_index: momentum,
    pressure_index: momentum,
    predictions,
    all_predictions: allPredictions,
    ai_score: computeAiScore(match, allPredictions),
    value_score: computeValueScore(match, allPredictions),
    reliability_score: allPredictions?.[0]?.reliability || 0,
    data_quality_score: statsCompleteness(stats).score,
    stats_completeness: statsCompleteness(stats),
    heat_level: computeHeatLevel(match),
    freshness_seconds: computeFreshness(updatedAt || (/* @__PURE__ */ new Date()).toISOString())
  };
}
async function cacheLiveMatches(rawMatches, updatedAt = nowIso()) {
  if (!rawMatches?.length) return;
  const rows = rawMatches.map((m) => {
    const normalized = normalizeMatch(m, updatedAt);
    return {
      id: String(m.id),
      home_team: m.home_team ?? null,
      away_team: m.away_team ?? null,
      home_score: m.home_score ?? 0,
      away_score: m.away_score ?? 0,
      current_minute: m.current_minute ?? 0,
      league_name: m.league?.name ?? m.league_name ?? null,
      status: m.status ?? null,
      raw_data: normalized,
      momentum: normalized.momentum_index ?? null,
      updated_at: updatedAt
    };
  });
  const { error } = await supabase.from("matches_live").upsert(rows);
  if (error) throw error;
}
async function findExistingPredictionId(params) {
  let q = supabase.from("live_predictions").select("id").eq("match_id", params.match_id).eq("prediction_type", params.prediction_type).eq("threshold", params.threshold).order("created_at", { ascending: false }).limit(1);
  if (params.validated === true || params.validated === false) {
    q = q.eq("validated", params.validated);
  }
  const { data, error } = await q.maybeSingle();
  if (error) throw error;
  return data?.id ?? null;
}
async function claimTelegramDelivery(predictionId) {
  const id = String(predictionId);
  const claimedAt = nowIso();
  const { data, error } = await supabase.from("live_predictions").update({
    telegram_sent: true,
    telegram_last_attempt_at: claimedAt,
    telegram_last_error: "__SENDING__"
  }).eq("id", id).or("telegram_sent.is.null,telegram_sent.eq.false").select("id").maybeSingle();
  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("\u26A0\uFE0F Verrou Telegram indisponible: colonnes retry absentes.");
      return false;
    }
    console.error("\u26A0\uFE0F Claim Telegram impossible:", id, error);
    return false;
  }
  return Boolean(data?.id);
}
async function releaseStaleTelegramClaims() {
  const staleBefore = new Date(Date.now() - 5 * 60 * 1e3).toISOString();
  const { error } = await supabase.from("live_predictions").update({
    telegram_sent: false,
    telegram_last_error: "Claim Telegram expir\xE9, nouvel essai autoris\xE9"
  }).eq("telegram_sent", true).eq("telegram_last_error", "__SENDING__").lt("telegram_last_attempt_at", staleBefore);
  if (error && !isUndefinedColumnError(error)) {
    console.warn("\u26A0\uFE0F Nettoyage claims Telegram impossible:", error);
  }
}
async function markTelegramDelivery(predictionId, delivery) {
  const id = String(predictionId);
  const { data: row, error: readError } = await supabase.from("live_predictions").select("telegram_attempts").eq("id", id).maybeSingle();
  if (readError) {
    if (isUndefinedColumnError(readError)) {
      console.warn("\u26A0\uFE0F Colonnes Telegram retry absentes. Ex\xE9cute telegram_retry_migration.sql.");
      return false;
    }
    console.error("\u26A0\uFE0F Lecture telegram_attempts impossible:", readError);
    return false;
  }
  const attemptAt = nowIso();
  const values2 = {
    telegram_sent: delivery.ok,
    telegram_attempts: safeNumber(row?.telegram_attempts, 0) + 1,
    telegram_last_attempt_at: attemptAt,
    telegram_last_error: delivery.ok ? null : delivery.error || "\xC9chec de l'envoi Telegram",
    telegram_pending_chat_ids: delivery.ok ? [] : delivery.failedChatIds
  };
  if (delivery.ok) values2.telegram_sent_at = attemptAt;
  const { error } = await supabase.from("live_predictions").update(values2).eq("id", id);
  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("\u26A0\uFE0F Colonnes Telegram retry absentes. Ex\xE9cute telegram_retry_migration.sql.");
      return false;
    }
    console.error("\u26A0\uFE0F Mise \xE0 jour du statut Telegram impossible:", error);
    return false;
  }
  return true;
}
async function processTelegramPredictionById(predictionId) {
  const id = String(predictionId || "").trim();
  if (!id) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      error: "prediction_id manquant"
    };
  }
  await releaseStaleTelegramClaims();
  const { data: row, error } = await supabase.from("live_predictions").select(
    "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, confidence, validated, telegram_sent, telegram_attempts, telegram_last_error, telegram_last_attempt_at, telegram_pending_chat_ids, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa"
  ).eq("id", id).maybeSingle();
  if (error) {
    if (isUndefinedColumnError(error)) {
      return {
        telegram_retry_enabled: false,
        telegram_retry_processed: 0,
        telegram_retry_sent: 0,
        telegram_retry_failed: 1,
        telegram_retry_skipped: 0,
        error: "colonnes Telegram retry absentes"
      };
    }
    throw error;
  }
  if (!row) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      error: "prediction introuvable"
    };
  }
  if (row.validated === true) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      error: "prediction d\xE9j\xE0 valid\xE9e"
    };
  }
  if (row.telegram_sent === true && row.telegram_last_error !== "__SENDING__") {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_sent: true
    };
  }
  const currentMatch = await getTelegramMatchFromCache(row, null);
  if (!currentMatch) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 1,
      telegram_retry_skipped: 0,
      error: "match introuvable dans le cache LIVE"
    };
  }
  const retryMatch = {
    ...currentMatch,
    home_team: row.home_team ?? currentMatch.home_team,
    away_team: row.away_team ?? currentMatch.away_team,
    home_score: row.home_score ?? currentMatch.home_score ?? 0,
    away_score: row.away_score ?? currentMatch.away_score ?? 0,
    current_minute: row.minute ?? currentMatch.current_minute ?? 0,
    league_name: row.league_name ?? currentMatch.league_name ?? currentMatch?.league?.name,
    league: {
      ...currentMatch?.league || {},
      name: row.league_name ?? currentMatch?.league?.name ?? "Football"
    }
  };
  const retryPred = {
    ...row,
    type: row.prediction_type,
    prediction_type: row.prediction_type,
    pronostic: row.threshold,
    signal_value: row.projected_value ?? row.current_value ?? 0,
    current: row.projected_value ?? row.current_value ?? 0
  };
  const claimed = await claimTelegramDelivery(row.id);
  if (!claimed) {
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 0,
      telegram_retry_sent: 0,
      telegram_retry_failed: 0,
      telegram_retry_skipped: 1,
      already_claimed: true
    };
  }
  const pendingChatIds = Array.isArray(row.telegram_pending_chat_ids) ? row.telegram_pending_chat_ids.map((chatId) => String(chatId || "").trim()).filter(Boolean) : [];
  try {
    const delivery = await sendTelegramLiveCoupon(
      retryMatch,
      retryPred,
      row.id,
      pendingChatIds.length ? pendingChatIds : void 0
    );
    await markTelegramDelivery(row.id, delivery);
    return {
      telegram_retry_enabled: true,
      telegram_retry_processed: 1,
      telegram_retry_sent: delivery.ok ? 1 : 0,
      telegram_retry_failed: delivery.ok ? 0 : 1,
      telegram_retry_skipped: 0,
      prediction_id: row.id,
      sent_chat_ids: delivery.sentChatIds,
      failed_chat_ids: delivery.failedChatIds,
      error: delivery.error
    };
  } catch (e) {
    const failedTargets = pendingChatIds.length ? pendingChatIds : telegramChatIds();
    await markTelegramDelivery(row.id, {
      ok: false,
      sentChatIds: [],
      failedChatIds: failedTargets,
      error: e?.message || String(e)
    });
    throw e;
  }
}
async function retryPendingTelegramLiveCoupons(liveMatchesNormalized, maxToProcess = 1) {
  const emptyResult = {
    telegram_retry_enabled: true,
    telegram_retry_processed: 0,
    telegram_retry_sent: 0,
    telegram_retry_failed: 0,
    telegram_retry_skipped: 0
  };
  if (maxToProcess <= 0) return emptyResult;
  await releaseStaleTelegramClaims();
  const { data: pending, error } = await supabase.from("live_predictions").select(
    "id, match_id, match_name, home_team, away_team, home_score, away_score, minute, league_name, prediction_type, probability, message, threshold, projected_value, current_value, confidence, validated, telegram_sent, telegram_attempts, telegram_pending_chat_ids, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa"
  ).eq("validated", false).order("created_at", { ascending: true }).limit(50);
  if (error) {
    if (isUndefinedColumnError(error)) {
      console.warn("\u26A0\uFE0F Retry Telegram d\xE9sactiv\xE9: migration SQL non appliqu\xE9e.");
      return { ...emptyResult, telegram_retry_enabled: false };
    }
    console.error("\u26A0\uFE0F Lecture des envois Telegram \xE0 retenter impossible:", error);
    return { ...emptyResult, telegram_retry_failed: 1 };
  }
  const eligible = (pending || []).filter(
    (row) => row?.telegram_sent !== true && safeNumber(row?.telegram_attempts, 0) < 5
  );
  if (!eligible.length) return emptyResult;
  const liveMap = /* @__PURE__ */ new Map();
  for (const match of liveMatchesNormalized || []) {
    liveMap.set(String(match.id), match);
  }
  let processed = 0;
  for (const row of eligible) {
    if (processed >= maxToProcess) break;
    let currentMatch = liveMap.get(String(row.match_id));
    if (!currentMatch) {
      currentMatch = await getTelegramMatchFromCache(row, null);
    }
    if (!currentMatch) {
      emptyResult.telegram_retry_skipped++;
      continue;
    }
    const retryMatch = {
      ...currentMatch,
      home_team: row.home_team ?? currentMatch.home_team,
      away_team: row.away_team ?? currentMatch.away_team,
      home_score: row.signal_home_score ?? row.home_score ?? currentMatch.home_score ?? 0,
      away_score: row.signal_away_score ?? row.away_score ?? currentMatch.away_score ?? 0,
      current_minute: row.signal_minute ?? row.minute ?? currentMatch.current_minute ?? 0,
      league_name: row.league_name ?? currentMatch.league_name ?? currentMatch?.league?.name,
      league: {
        ...currentMatch?.league || {},
        name: row.league_name ?? currentMatch?.league?.name ?? "Football"
      }
    };
    const retryPred = {
      ...row,
      type: row.prediction_type,
      prediction_type: row.prediction_type,
      pronostic: row.threshold,
      signal_value: row.projected_value ?? row.current_value ?? 0,
      current: row.projected_value ?? row.current_value ?? 0
    };
    const claimed = await claimTelegramDelivery(row.id);
    if (!claimed) {
      emptyResult.telegram_retry_skipped++;
      continue;
    }
    processed++;
    emptyResult.telegram_retry_processed++;
    try {
      const pendingChatIds = Array.isArray(row.telegram_pending_chat_ids) ? row.telegram_pending_chat_ids.map((id) => String(id || "").trim()).filter(Boolean) : [];
      const delivery = await sendTelegramLiveCoupon(
        retryMatch,
        retryPred,
        row.id,
        pendingChatIds.length ? pendingChatIds : void 0
      );
      await markTelegramDelivery(row.id, delivery);
      if (delivery.ok) emptyResult.telegram_retry_sent++;
      else emptyResult.telegram_retry_failed++;
    } catch (e) {
      emptyResult.telegram_retry_failed++;
      const failedTargets = Array.isArray(row.telegram_pending_chat_ids) && row.telegram_pending_chat_ids.length ? row.telegram_pending_chat_ids.map(String) : telegramChatIds();
      await markTelegramDelivery(row.id, {
        ok: false,
        sentChatIds: [],
        failedChatIds: failedTargets,
        error: e?.message || String(e)
      });
      console.error("\u274C Retry Telegram LIVE impossible:", row.id, e);
    }
  }
  return emptyResult;
}
var LIVE_COUPON_STAKE_FCFA = 5e5;
var formatReceiptOdds = (n) => n.toFixed(2);
var formatReceiptMoney = (n) => formatTelegramMoney(n);
async function fetchExternalLivePropOdds(match, pred) {
  const direct = (Deno.env.get("LIVE_ODDS_ENABLE_DIRECT") || "1") === "1" ? await fetchLiveBookmakerOdds({
    match_id: String(match?.id ?? ""),
    home: String(match?.home_team?.name ?? match?.home_team ?? match?.home_name ?? ""),
    away: String(match?.away_team?.name ?? match?.away_team ?? match?.away_name ?? ""),
    kickoff: String(match?.event_date ?? match?.start_time ?? match?.kickoff ?? ""),
    market: String(pred?.type ?? pred?.prediction_type ?? ""),
    line: Number(pred?.threshold),
    minute: Number(pred?.minute ?? match?.current_minute ?? 0)
  }, supabase) : null;
  if (direct) return direct;
  const verified = await fetchFiveSourceLiveOdds({
    match_id: String(match?.id ?? ""),
    home: String(match?.home_team?.name ?? match?.home_team ?? match?.home_name ?? ""),
    away: String(match?.away_team?.name ?? match?.away_team ?? match?.away_name ?? ""),
    kickoff: String(match?.event_date ?? match?.start_time ?? match?.kickoff ?? ""),
    market: String(pred?.type ?? pred?.prediction_type ?? ""),
    line: Number(pred?.threshold),
    minute: Number(pred?.minute ?? match?.current_minute ?? 0)
  });
  if (verified) return verified;
  if (!LIVE_PROP_ODDS_URL) return null;
  try {
    const requestedLine = Number(pred?.threshold);
    const url2 = new URL(LIVE_PROP_ODDS_URL);
    url2.searchParams.set("match_id", String(match?.id ?? ""));
    url2.searchParams.set("market", String(pred?.type ?? pred?.prediction_type ?? ""));
    url2.searchParams.set("line", String(pred?.threshold ?? ""));
    url2.searchParams.set("minute", String(pred?.minute ?? match?.current_minute ?? 0));
    const headers = { Accept: "application/json" };
    if (LIVE_PROP_ODDS_TOKEN) headers.Authorization = "Bearer " + LIVE_PROP_ODDS_TOKEN;
    const res = await fetch(url2.toString(), { headers });
    if (!res.ok) return null;
    const body = await res.json().catch(() => null);
    const raw = body?.odds ?? body?.price ?? body?.decimal_odds ?? body?.data?.odds ?? body?.data?.price ?? body?.data?.decimal_odds;
    const odds = Number(raw);
    if (!Number.isFinite(odds) || odds <= 1.01 || odds > 25) return null;
    const returnedLineRaw = body?.line ?? body?.threshold ?? body?.market_line ?? body?.point ?? body?.data?.line ?? body?.data?.threshold ?? body?.data?.market_line ?? body?.data?.point;
    const returnedLine = Number(returnedLineRaw);
    if (Number.isFinite(returnedLine) && Number.isFinite(requestedLine) && Math.abs(returnedLine - requestedLine) > 0.01) {
      console.log("Bookmaker line mismatch", {
        match_id: match?.id,
        market: pred?.type ?? pred?.prediction_type,
        requested_line: requestedLine,
        returned_line: returnedLine
      });
      return null;
    }
    return {
      odds: Number(odds.toFixed(2)),
      source: String(body?.source || body?.bookmaker || "external_live"),
      line: Number.isFinite(returnedLine) ? Number(returnedLine.toFixed(1)) : Number.isFinite(requestedLine) ? Number(requestedLine.toFixed(1)) : null
    };
  } catch (e) {
    console.warn("LIVE prop odds provider unavailable:", e);
    return null;
  }
}
function minimumBookmakerEdge(tier) {
  return tier === "high_value" ? 0.12 : tier === "value" ? 0.08 : 0.05;
}
function bookmakerCandidateList(pred) {
  const selectedThreshold = Number(pred?.threshold);
  const raw = Array.isArray(pred?.line_candidates) ? pred.line_candidates : [];
  const unique = /* @__PURE__ */ new Map();
  for (const item of raw) {
    const threshold = Number(item?.threshold);
    if (!Number.isFinite(threshold)) continue;
    unique.set(Number(threshold.toFixed(1)), {
      ...item,
      threshold: Number(threshold.toFixed(1))
    });
  }
  if (Number.isFinite(selectedThreshold) && !unique.has(Number(selectedThreshold.toFixed(1)))) {
    unique.set(Number(selectedThreshold.toFixed(1)), {
      threshold: Number(selectedThreshold.toFixed(1)),
      probability: safeNumber(pred?.probability, 0.5),
      model_fair_odds: safeNumber(
        pred?.model_fair_odds,
        estimatedModelOdds(safeNumber(pred?.probability, 0.5))
      ),
      signal_tier: pred?.signal_tier ?? null
    });
  }
  return [...unique.values()].sort((a, b2) => {
    const da = Math.abs(Number(a.threshold) - selectedThreshold);
    const db2 = Math.abs(Number(b2.threshold) - selectedThreshold);
    if (Math.abs(da - db2) > 1e-9) return da - db2;
    return Number(a.threshold) - Number(b2.threshold);
  });
}
function applyBookmakerCandidate(pred, candidate) {
  const threshold = Number(candidate.threshold.toFixed(1));
  pred.threshold = threshold;
  pred.probability = Number(safeNumber(candidate.probability, pred.probability).toFixed(4));
  pred.model_fair_odds = Number(
    safeNumber(candidate.model_fair_odds, estimatedModelOdds(pred.probability)).toFixed(2)
  );
  pred.signal_tier = candidate.signal_tier ?? signalTierFromModelOdds(pred.model_fair_odds);
  const unit = pred?.type === "total_corners" ? "corners" : pred?.type === "total_shots" ? "tirs" : pred?.type === "total_fouls" ? "fautes" : "";
  pred.title = unit ? `Over ${threshold} ${unit}` : `Over ${threshold}`;
  if (Array.isArray(pred?.line_candidates)) {
    const rank = pred.line_candidates.findIndex(
      (c) => Math.abs(Number(c?.threshold) - threshold) < 0.01
    );
    if (rank >= 0) pred.line_candidate_rank = rank + 1;
  }
  if (pred?.baseline_threshold != null) {
    pred.selected_uplift = Number((threshold - Number(pred.baseline_threshold)).toFixed(2));
  }
  if (!Array.isArray(pred.reasons)) pred.reasons = [];
  pred.reasons.push(`Ligne bookmaker v\xE9rifi\xE9e ${threshold}`);
}
async function alignPredictionToAvailableBookmakerLine(match, pred) {
  const explicit = pickTelegramNumber(pred?.bookmaker_odds, pred?.external_live_odds);
  if (explicit !== null && explicit > 1) {
    return {
      verified: true,
      external: {
        odds: Number(explicit.toFixed(2)),
        source: "provided_bookmaker",
        line: Number(safeNumber(pred?.threshold, 0).toFixed(1))
      },
      candidate: null
    };
  }
  if (!LIVE_PROP_ODDS_URL && !["MOVIODDS", "PINNWIRE", "ODDSLINK", "GOALDIR", "ODDSHARVESTER"].some((p) => Deno.env.get("LIVE_ODDS_" + p + "_URL")) && Deno.env.get("LIVE_ODDS_ENABLE_DIRECT") !== "1") {
    return {
      verified: false,
      external: null,
      candidate: null,
      reason: "bookmaker_line_source_unavailable"
    };
  }
  for (const candidate of bookmakerCandidateList(pred)) {
    const probePred = { ...pred, threshold: candidate.threshold };
    const external = await fetchExternalLivePropOdds(match, probePred);
    if (!external) continue;
    const probability = Math.min(
      0.95,
      Math.max(0.05, safeNumber(candidate?.probability, pred?.probability ?? 0.5))
    );
    const implied = 1 / external.odds;
    const edge = probability - implied;
    const ev = probability * external.odds - 1;
    const tier = candidate?.signal_tier ?? pred?.signal_tier ?? null;
    if (edge < minimumBookmakerEdge(tier) || ev <= 0) {
      console.log("Bookmaker line available but rejected on value", {
        match_id: match?.id,
        market: pred?.type,
        threshold: candidate.threshold,
        odds: external.odds,
        edge: Number(edge.toFixed(4)),
        ev: Number(ev.toFixed(4))
      });
      continue;
    }
    return { verified: true, external, candidate };
  }
  return {
    verified: false,
    external: null,
    candidate: null,
    reason: "no_model_bookmaker_line_intersection"
  };
}
async function computeLiveCouponPricing(match, pred, forcedExternal = null) {
  const probability = Math.min(0.95, Math.max(0.05, safeNumber(pred?.probability, 0.5)));
  const modelFairOdds = Number(safeNumber(pred?.model_fair_odds, estimatedModelOdds(probability)).toFixed(2));
  const explicit = pickTelegramNumber(pred?.bookmaker_odds, pred?.external_live_odds);
  const external = explicit !== null && explicit > 1 ? { odds: Number(explicit.toFixed(2)), source: "provided_bookmaker", line: Number(pred?.threshold) } : forcedExternal ?? await fetchExternalLivePropOdds(match, pred);
  const bookmakerOdds = external?.odds ?? null;
  const rawDisplayOdds = bookmakerOdds ?? modelFairOdds;
  const receiptOdds = Number(Math.min(3.2, Math.max(1.05, rawDisplayOdds)).toFixed(2));
  const impliedProbability = bookmakerOdds ? Number((1 / bookmakerOdds).toFixed(6)) : null;
  const edge = impliedProbability != null ? Number((probability - impliedProbability).toFixed(6)) : null;
  const expectedValue = bookmakerOdds ? Number((probability * bookmakerOdds - 1).toFixed(6)) : null;
  return {
    odds: receiptOdds,
    potentialGain: Math.round(LIVE_COUPON_STAKE_FCFA * receiptOdds),
    source: external ? external.source : "model_fair_odds",
    pricingMode: external ? "external_live" : "model_only",
    modelFairOdds,
    bookmakerOdds,
    impliedProbability,
    edge,
    expectedValue
  };
}
function signalPeriodCapture(match) {
  const raw = match?.raw_data ?? match?.raw ?? match ?? {};
  const first = (...vs) => {
    for (const v of vs) if (v !== null && v !== void 0 && v !== "" && Number.isFinite(Number(v))) return Number(v);
    return null;
  };
  return {
    signal_half1_home: first(raw?.ht_home, raw?.home_ht, raw?.halftime_home, raw?.first_half_home),
    signal_half1_away: first(raw?.ht_away, raw?.away_ht, raw?.halftime_away, raw?.first_half_away),
    signal_half2_home: first(raw?.sh_home, raw?.home_sh, raw?.second_half_home, raw?.period2_home),
    signal_half2_away: first(raw?.sh_away, raw?.away_sh, raw?.second_half_away, raw?.period2_away)
  };
}
async function savePrediction(match, pred, options = {}) {
  const matchId = String(match.id);
  const signalValue = safeNumber(pred.signal_value ?? pred.current, 0);
  pred.minute = pred.minute ?? match.current_minute ?? 0;
  pred.projected_value = pred.projected_value ?? signalValue;
  pred.signal_value = pred.signal_value ?? signalValue;
  pred.home_score = pred.home_score ?? match.home_score ?? 0;
  pred.away_score = pred.away_score ?? match.away_score ?? 0;
  const bookmakerAlignment = LIVE_PROP_ODDS_URL || (Deno.env.get("LIVE_ODDS_ENABLE_DIRECT") || "1") === "1" || ["MOVIODDS", "PINNWIRE", "ODDSLINK", "GOALDIR", "ODDSHARVESTER"].some((p) => Deno.env.get("LIVE_ODDS_" + p + "_URL")) ? await alignPredictionToAvailableBookmakerLine(match, pred) : {
    verified: false,
    external: null,
    candidate: null,
    reason: "bookmaker_line_source_unavailable"
  };
  if (LIVE_REQUIRE_BOOKMAKER_LINE && !bookmakerAlignment.verified) {
    console.log("Signal rejected: no playable bookmaker line", {
      match_id: matchId,
      market: pred?.type,
      model_line: pred?.threshold,
      reason: bookmakerAlignment.reason
    });
    return {
      created: false,
      id: null,
      skipped: bookmakerAlignment.reason || "bookmaker_line_unavailable"
    };
  }
  if (bookmakerAlignment.candidate) {
    applyBookmakerCandidate(pred, bookmakerAlignment.candidate);
  }
  const thresholdNum = Number(safeNumber(pred.threshold, 0).toFixed(1));
  const livePricing = await computeLiveCouponPricing(
    match,
    pred,
    bookmakerAlignment.external
  );
  pred.live_odds = livePricing.odds;
  pred.model_fair_odds = livePricing.modelFairOdds;
  pred.bookmaker_odds = livePricing.bookmakerOdds;
  pred.implied_probability = livePricing.impliedProbability;
  pred.edge = livePricing.edge;
  pred.expected_value = livePricing.expectedValue;
  pred.pricing_mode = livePricing.pricingMode;
  pred.stake_fcfa = LIVE_COUPON_STAKE_FCFA;
  pred.potential_gain_fcfa = livePricing.potentialGain;
  if (livePricing.pricingMode === "external_live") {
    const minEdge = minimumBookmakerEdge(pred.signal_tier);
    const edge = safeNumber(livePricing.edge, -1);
    const ev = safeNumber(livePricing.expectedValue, -1);
    if (edge < minEdge || ev <= 0) {
      console.log("Value gate: signal rejected against bookmaker price", { match_id: matchId, threshold: thresholdNum, edge, ev, minEdge });
      return { created: false, id: null, skipped: "no_bookmaker_value" };
    }
  }
  const payload = {
    match_id: matchId,
    match_name: `${match.home_team} vs ${match.away_team}`,
    home_team: match.home_team ?? null,
    away_team: match.away_team ?? null,
    home_score: pred.home_score,
    away_score: pred.away_score,
    signal_home_score: pred.home_score,
    signal_away_score: pred.away_score,
    signal_minute: pred.minute,
    ...signalPeriodCapture(match),
    live_odds: livePricing.odds,
    stake_fcfa: LIVE_COUPON_STAKE_FCFA,
    potential_gain_fcfa: livePricing.potentialGain,
    odds_source: livePricing.source,
    minute: pred.minute,
    league_name: match.league?.name ?? match.league_name ?? null,
    prediction_type: pred.type,
    probability: pred.probability,
    message: pred.message,
    threshold: thresholdNum,
    signal_value: signalValue,
    projected_value: safeNumber(pred.projected_value, signalValue),
    current_value: signalValue,
    reliability_score: safeNumber(pred.reliability, 0),
    model_fair_odds: livePricing.modelFairOdds,
    bookmaker_odds: livePricing.bookmakerOdds,
    implied_probability: livePricing.impliedProbability,
    edge: livePricing.edge,
    expected_value: livePricing.expectedValue,
    value_score: computeValueScore(match, [{ ...pred, bookmaker_odds: livePricing.bookmakerOdds }]),
    data_quality_score: safeNumber(pred.data_quality_score, match?.data_quality_score ?? 0),
    freshness_seconds: Number.isFinite(safeNumber(pred.freshness_seconds, NaN)) ? safeNumber(pred.freshness_seconds, 0) : null,
    source_count: safeNumber(pred.source_count, 1),
    source_confidence: safeNumber(pred.source_confidence, 0),
    source_agreement_score: pred.source_agreement_score ?? null,
    signal_tier: pred.signal_tier ?? null,
    pricing_mode: livePricing.pricingMode,
    line_candidate_count: safeNumber(pred.line_candidate_count, 0),
    line_candidate_rank: safeNumber(pred.line_candidate_rank, 0),
    line_candidates: pred.line_candidates ?? null,
    baseline_threshold: pred.baseline_threshold ?? null,
    historical_uplift_cap: pred.historical_uplift_cap ?? null,
    selected_uplift: pred.selected_uplift ?? null,
    model_version: pred.model_version ?? LIVE_VALUE_MODEL_VERSION,
    confidence: safeNumber(pred.reliability, 0) >= 80 ? "high" : "medium",
    validated: false,
    outcome: null,
    telegram_sent: false,
    telegram_attempts: 0,
    telegram_last_attempt_at: null,
    telegram_last_error: null,
    telegram_pending_chat_ids: telegramChatIds(),
    updated_at: (/* @__PURE__ */ new Date()).toISOString()
  };
  const existingRunning = await findExistingPredictionId({
    match_id: matchId,
    prediction_type: pred.type,
    threshold: thresholdNum,
    validated: false
  });
  if (existingRunning) return { created: false, id: existingRunning };
  let { data, error } = await supabase.from("live_predictions").insert({ ...payload, created_at: (/* @__PURE__ */ new Date()).toISOString() }).select("id").single();
  if (error && isUndefinedColumnError(error)) {
    const legacyPayload = { ...payload };
    for (const key of ["signal_value", "reliability_score", "model_fair_odds", "bookmaker_odds", "implied_probability", "edge", "expected_value", "value_score", "data_quality_score", "freshness_seconds", "source_count", "source_confidence", "source_agreement_score", "signal_tier", "pricing_mode", "line_candidate_count", "line_candidate_rank", "line_candidates", "baseline_threshold", "historical_uplift_cap", "selected_uplift", "model_version", "final_value", "headroom"]) delete legacyPayload[key];
    const retry = await supabase.from("live_predictions").insert({ ...legacyPayload, created_at: (/* @__PURE__ */ new Date()).toISOString() }).select("id").single();
    data = retry.data;
    error = retry.error;
  }
  if (error) {
    if (isDuplicateKeyError(error)) {
      const id2 = await findExistingPredictionId({
        match_id: matchId,
        prediction_type: pred.type,
        threshold: thresholdNum,
        validated: false
      }) ?? await findExistingPredictionId({
        match_id: matchId,
        prediction_type: pred.type,
        threshold: thresholdNum,
        validated: null
      });
      return { created: false, id: id2 };
    }
    throw error;
  }
  if (!data?.id) throw new Error("Insertion live_predictions sans id retourn\xE9");
  const predictionId = String(data.id);
  try {
    await insertNotification({
      user_id: "all",
      type: "live_prediction",
      title: "Nouvelle opportunit\xE9 LIVE",
      message: `${payload.match_name}
Pronostic: ${pred.title}
Minute du signal: ${payload.minute}'
Pronostic (seuil): ${payload.threshold}
Au signal: ${signalValue}
Cote ${livePricing.pricingMode === "external_live" ? "bookmaker" : "mod\xE8le"}: ${formatReceiptOdds(livePricing.odds)}
Mise coupon: ${formatReceiptMoney(LIVE_COUPON_STAKE_FCFA)}`,
      priority: pred.probability >= 0.86 ? "urgent" : "normal",
      read: false,
      related_prediction_id: predictionId
    });
  } catch (e) {
    console.warn("Notification LIVE indisponible, Telegram continue:", e?.message || String(e));
  }
  let telegramAttempted = false;
  if (options.sendTelegram !== false) {
    const claimed = await claimTelegramDelivery(predictionId);
    if (claimed) {
      telegramAttempted = true;
      const telegramDelivery = await sendTelegramLiveCoupon(
        match,
        pred,
        predictionId
      );
      await markTelegramDelivery(predictionId, telegramDelivery);
    } else {
      console.log("\u23ED\uFE0F Envoi Telegram ignor\xE9: prediction d\xE9j\xE0 claim\xE9e", {
        prediction_id: predictionId
      });
    }
  } else {
    console.log("\u{1F4E5} Coupon LIVE mis en file Telegram", {
      prediction_id: predictionId
    });
  }
  return {
    created: true,
    id: predictionId,
    telegram_attempted: telegramAttempted
  };
}
async function updatePredictionSafe(predId, values2) {
  const { error } = await supabase.from("live_predictions").update(values2).eq("id", predId);
  if (!error) return true;
  if (isUndefinedColumnError(error)) {
    const cleaned = { ...values2 };
    delete cleaned.validation_type;
    delete cleaned.validated_at;
    delete cleaned.final_value;
    delete cleaned.headroom;
    const { error: e2 } = await supabase.from("live_predictions").update(cleaned).eq("id", predId);
    if (!e2) return true;
    throw e2;
  }
  throw error;
}
async function validatePredictionWithMerge(params) {
  const predId = String(params.predRow.id);
  const matchId = String(params.predRow.match_id);
  const pType = String(params.predRow.prediction_type);
  const threshold = Number(safeNumber(params.predRow.threshold, 0).toFixed(1));
  const values2 = {
    validated: true,
    outcome: params.outcome,
    current_value: params.currentValue,
    validated_at: (/* @__PURE__ */ new Date()).toISOString(),
    updated_at: (/* @__PURE__ */ new Date()).toISOString(),
    validation_type: params.validation_type
  };
  if (params.validation_type === "final") {
    values2.final_value = params.currentValue;
    values2.headroom = Number((params.currentValue - threshold).toFixed(2));
  }
  try {
    let { data, error } = await supabase.from("live_predictions").update(values2).eq("id", predId).eq("validated", false).select("id").maybeSingle();
    if (error && isUndefinedColumnError(error)) {
      const cleaned = { ...values2 };
      delete cleaned.validation_type;
      delete cleaned.validated_at;
      delete cleaned.final_value;
      delete cleaned.headroom;
      const retry = await supabase.from("live_predictions").update(cleaned).eq("id", predId).eq("validated", false).select("id").maybeSingle();
      data = retry.data;
      error = retry.error;
    }
    if (!error) {
      if (data?.id) return { id: String(data.id), transitioned: true };
      return { id: predId, transitioned: false };
    }
    if (!isDuplicateKeyError(error)) throw error;
    const existingValidatedId = await findExistingPredictionId({
      match_id: matchId,
      prediction_type: pType,
      threshold,
      validated: true
    });
    if (existingValidatedId) {
      await updatePredictionSafe(String(existingValidatedId), values2);
      const { error: delErr } = await supabase.from("live_predictions").delete().eq("id", predId);
      if (delErr) console.error("\u26A0\uFE0F delete duplicate pending pred failed:", delErr);
      return { id: String(existingValidatedId), transitioned: false };
    }
    console.error("\u26A0\uFE0F duplicate on validate but no existing validated row found. predId=", predId);
    return { id: predId, transitioned: false };
  } catch (e) {
    throw e;
  }
}
function computeCurrentValueFromStats(predType, stats) {
  if (!stats) return null;
  if (predType === "total_shots") {
    return safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
  }
  if (predType === "total_corners") {
    return safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
  }
  if (predType === "total_fouls") {
    return safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
  }
  return null;
}
async function validatePredictionsInPlay(liveMatchesNormalized, options = {}) {
  const liveMap = /* @__PURE__ */ new Map();
  for (const m of liveMatchesNormalized || []) liveMap.set(String(m.id), m);
  const { data: pending, error } = await supabase.from("live_predictions").select("id, match_id, match_name, prediction_type, threshold, validated, telegram_sent, created_at, signal_home_score, signal_away_score, signal_minute, signal_half1_home, signal_half1_away, signal_half2_home, signal_half2_away, live_odds, stake_fcfa, potential_gain_fcfa, pricing_mode, model_fair_odds, bookmaker_odds").eq("validated", false);
  if (error) throw error;
  if (!pending?.length) {
    return {
      instant_validated: 0,
      instant_validation_deferred: 0,
      updated_running: 0,
      skipped: 0
    };
  }
  const maxInstantValidations = Math.max(
    0,
    Math.floor(options.maxInstantValidations ?? 1)
  );
  let instantValidated = 0;
  let instantValidationDeferred = 0;
  let updatedRunning = 0;
  let skipped = 0;
  for (const pred of pending) {
    if (pred.telegram_sent !== true) {
      skipped++;
      continue;
    }
    const match = liveMap.get(String(pred.match_id));
    if (!match) {
      skipped++;
      continue;
    }
    const stats = match?.live_stats || null;
    const currentValue = computeCurrentValueFromStats(pred.prediction_type, stats);
    if (currentValue == null) {
      skipped++;
      continue;
    }
    await updatePredictionSafe(String(pred.id), {
      current_value: currentValue,
      updated_at: (/* @__PURE__ */ new Date()).toISOString()
    });
    updatedRunning++;
    const threshold = safeNumber(pred.threshold, 0);
    const reached = currentValue > threshold;
    if (!reached) continue;
    if (instantValidated >= maxInstantValidations) {
      instantValidationDeferred++;
      continue;
    }
    const validation = await validatePredictionWithMerge({
      predRow: pred,
      outcome: "success",
      currentValue,
      validation_type: "instant"
    });
    if (!validation.transitioned) {
      continue;
    }
    const keptId = validation.id;
    await insertNotification({
      user_id: "all",
      type: "prediction_reached",
      title: "Pronostic atteint en LIVE",
      message: `${match.home_team} vs ${match.away_team}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Actuel: ${currentValue}
Minute: ${match.current_minute ?? "-"}'`,
      priority: "normal",
      read: false,
      related_prediction_id: keptId
    });
    if (options.sendTelegram !== false) {
      await sendTelegramValidationResult(
        match,
        pred,
        "success",
        currentValue,
        "instant",
        keptId
      );
    }
    instantValidated++;
  }
  return {
    instant_validated: instantValidated,
    instant_validation_deferred: instantValidationDeferred,
    updated_running: updatedRunning,
    skipped
  };
}
function predictionMeta(type, threshold) {
  if (type === "total_corners") return { badge: "Corners", color: "yellow", title: `Over ${threshold} corners` };
  if (type === "total_shots") return { badge: "Tirs", color: "green", title: `Over ${threshold} tirs` };
  if (type === "total_fouls") return { badge: "Fautes", color: "orange", title: `Over ${threshold} fautes` };
  return { badge: "Signal", color: "gold", title: `Over ${threshold}` };
}
function predictionRowToUi(p) {
  const threshold = safeNumber(p.threshold, 0);
  const meta = predictionMeta(p.prediction_type, threshold);
  const signalValue = p.signal_value ?? p.current_value ?? null;
  const reliability = Math.round(safeNumber(p.reliability_score, (Number(p.probability) || 0) * 100));
  return {
    id: p.id,
    type: p.prediction_type,
    title: meta.title,
    badge: meta.badge,
    color: meta.color,
    probability: Number(p.probability) || 0,
    message: p.message,
    threshold,
    pronostic: threshold,
    current: p.current_value ?? null,
    signal_value: signalValue,
    projected: p.projected_value ?? null,
    projected_value: p.projected_value ?? null,
    reliability,
    model_fair_odds: p.model_fair_odds ?? null,
    bookmaker_odds: p.bookmaker_odds ?? null,
    implied_probability: p.implied_probability ?? null,
    edge: p.edge ?? null,
    expected_value: p.expected_value ?? null,
    value_score: p.value_score ?? null,
    data_quality_score: p.data_quality_score ?? null,
    freshness_seconds: p.freshness_seconds ?? null,
    source_count: p.source_count ?? null,
    source_confidence: p.source_confidence ?? null,
    source_agreement_score: p.source_agreement_score ?? null,
    signal_tier: p.signal_tier ?? null,
    pricing_mode: p.pricing_mode ?? null,
    line_candidate_count: p.line_candidate_count ?? null,
    line_candidate_rank: p.line_candidate_rank ?? null,
    baseline_threshold: p.baseline_threshold ?? null,
    historical_uplift_cap: p.historical_uplift_cap ?? null,
    selected_uplift: p.selected_uplift ?? null,
    model_version: p.model_version ?? null,
    final_value: p.final_value ?? null,
    headroom: p.headroom ?? null,
    reasons: [],
    confidence: p.confidence ?? null,
    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,
    created_at: p.created_at ?? null,
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
function actuFootEventPairKey(home, away) {
  return normalizeTeamKey(home) + "::" + normalizeTeamKey(away);
}
async function getRecentActuFootEvents(maxAgeSeconds = 6 * 3600) {
  const since = new Date(Date.now() - maxAgeSeconds * 1e3).toISOString();
  const { data, error } = await supabase.from("actu_foot_live_events").select("event_key,fixture_key,match_id,kind,priority_class,event_minute,score,home_team,away_team,league_name,provider_event_id,sources,payload,confirmed,first_seen_at,last_seen_at,event_at").gte("last_seen_at", since).eq("confirmed", true).order("first_seen_at", { ascending: true }).limit(500);
  if (error) {
    console.warn("actu_foot_live_events unavailable:", error.message);
    return [];
  }
  return data || [];
}
async function getLiveMatchesFromDb(maxAgeSeconds = 240) {
  const since = new Date(Date.now() - maxAgeSeconds * 1e3).toISOString();
  const { data: rows, error } = await supabase.from("matches_live").select("id, raw_data, updated_at").gte("updated_at", since).order("updated_at", { ascending: false });
  if (error) throw error;
  const matchesRows = rows || [];
  const ids = matchesRows.map((r) => String(r.id));
  if (!ids.length) return [];
  const { data: preds, error: predErr } = await supabase.from("live_predictions").select("*").in("match_id", ids).eq("validated", false).order("created_at", { ascending: false });
  if (predErr) throw predErr;
  const eventRows = await getRecentActuFootEvents();
  const eventsByPair = /* @__PURE__ */ new Map();
  for (const event of eventRows) {
    const pair = actuFootEventPairKey(event?.home_team, event?.away_team);
    if (!pair || pair === "::") continue;
    if (!eventsByPair.has(pair)) eventsByPair.set(pair, []);
    eventsByPair.get(pair).push({
      event_key: event.event_key,
      fixture_key: event.fixture_key,
      match_id: event.match_id,
      kind: event.kind,
      priority_class: event.priority_class,
      minute: event.event_minute,
      score: event.score,
      player: event?.payload?.player || event?.payload?.goal?.player || "",
      team: event?.payload?.team || "",
      entrant: event?.payload?.entrant || "",
      sortant: event?.payload?.sortant || "",
      shootout_scores: event?.payload?.shootout_scores || [],
      sources: event.sources || [],
      first_seen_at: event.first_seen_at,
      event_at: event.event_at
    });
  }
  const byMatch = /* @__PURE__ */ new Map();
  for (const p of preds || []) {
    const k = String(p.match_id);
    if (!byMatch.has(k)) byMatch.set(k, []);
    byMatch.get(k).push(p);
  }
  const out = matchesRows.map((r) => {
    const base = r.raw_data || {};
    const pRows = byMatch.get(String(r.id)) || [];
    const uiPreds = pRows.map(predictionRowToUi);
    uiPreds.sort((a, b2) => {
      const dv = safeNumber(b2.value_score, 0) - safeNumber(a.value_score, 0);
      if (dv !== 0) return dv;
      return safeNumber(b2.reliability, 0) - safeNumber(a.reliability, 0);
    });
    const pair = actuFootEventPairKey(base?.home_team, base?.away_team);
    const matchEvents = eventsByPair.get(pair) || [];
    return {
      ...base,
      predictions: uiPreds,
      all_predictions: uiPreds,
      events: matchEvents,
      freshness_seconds: computeFreshness(r.updated_at),
      updated_at: r.updated_at
    };
  });
  out.sort((a, b2) => safeNumber(b2.value_score) - safeNumber(a.value_score));
  return out;
}
async function getLiveOpportunitiesFromDb() {
  const matches = await getLiveMatchesFromDb();
  const withPred = matches.filter((m) => Array.isArray(m.predictions) && m.predictions.length > 0);
  withPred.sort((a, b2) => {
    const av = safeNumber(a?.predictions?.[0]?.value_score, a?.value_score);
    const bv = safeNumber(b2?.predictions?.[0]?.value_score, b2?.value_score);
    if (bv !== av) return bv - av;
    const ar = safeNumber(a?.predictions?.[0]?.reliability, 0);
    const br = safeNumber(b2?.predictions?.[0]?.reliability, 0);
    if (br !== ar) return br - ar;
    return safeNumber(b2?.predictions?.[0]?.probability, 0) - safeNumber(a?.predictions?.[0]?.probability, 0);
  });
  return withPred.slice(0, 12);
}
function oddsBucket(value) {
  if (value == null || !Number.isFinite(value)) return null;
  if (value >= 1.5 && value <= 1.75) return "1.50-1.75";
  if (value > 1.75 && value <= 2) return "1.76-2.00";
  if (value > 2 && value <= 2.5) return "2.01-2.50";
  if (value > 2.5 && value <= 3) return "2.51-3.00";
  if (value > 3 && value <= 3.2) return "3.01-3.20";
  return null;
}
function summarizeBacktestRows(rows) {
  const shifts = [0, 1, 2, 3];
  const shiftStats = {};
  for (const shift of shifts) {
    const eligible = rows.filter((r) => Number.isFinite(Number(r.final_value ?? r.current_value)) && Number.isFinite(Number(r.threshold)));
    const wins = eligible.filter((r) => Number(r.final_value ?? r.current_value) > Number(r.threshold) + shift).length;
    shiftStats["plus_" + shift] = { signals: eligible.length, wins, losses: eligible.length - wins, hit_rate: eligible.length ? Number((wins / eligible.length * 100).toFixed(2)) : 0 };
  }
  const byMarket = {};
  for (const market of ["total_corners", "total_shots", "total_fouls"]) {
    const subset = rows.filter((r) => r.prediction_type === market);
    const usable = subset.filter((r) => Number.isFinite(Number(r.final_value ?? r.current_value)) && Number.isFinite(Number(r.threshold)));
    const headrooms = usable.map((r) => Number(r.final_value ?? r.current_value) - Number(r.threshold));
    const wins = headrooms.filter((h) => h > 0).length;
    byMarket[market] = {
      signals: usable.length,
      wins,
      losses: usable.length - wins,
      hit_rate: usable.length ? Number((wins / usable.length * 100).toFixed(2)) : 0,
      average_headroom: headrooms.length ? Number((headrooms.reduce((a, b2) => a + b2, 0) / headrooms.length).toFixed(2)) : null,
      median_headroom: headrooms.length ? Number([...headrooms].sort((a, b2) => a - b2)[Math.floor((headrooms.length - 1) / 2)].toFixed(2)) : null
    };
  }
  const bucketSummary = (field) => {
    const out = {};
    for (const name of ["1.50-1.75", "1.76-2.00", "2.01-2.50", "2.51-3.00", "3.01-3.20"]) {
      const subset = rows.filter((r) => oddsBucket(Number(r?.[field])) === name);
      const usable = subset.filter((r) => Number.isFinite(Number(r.final_value ?? r.current_value)) && Number.isFinite(Number(r.threshold)));
      const wins = usable.filter((r) => Number(r.final_value ?? r.current_value) > Number(r.threshold)).length;
      const returns = field === "bookmaker_odds" ? usable.reduce((sum, r) => sum + (Number(r.final_value ?? r.current_value) > Number(r.threshold) ? Number(r.bookmaker_odds) : 0), 0) : null;
      out[name] = {
        signals: usable.length,
        wins,
        losses: usable.length - wins,
        hit_rate: usable.length ? Number((wins / usable.length * 100).toFixed(2)) : 0,
        roi: returns != null && usable.length ? Number(((returns / usable.length - 1) * 100).toFixed(2)) : null
      };
    }
    return out;
  };
  const v2Rows = rows.filter((r) => r.model_version === LIVE_VALUE_MODEL_VERSION && Array.isArray(r.line_candidates));
  let medianWins = 0;
  let medianUsable = 0;
  for (const r of v2Rows) {
    const candidates = r.line_candidates || [];
    const selected = selectMedianCandidate(candidates);
    const finalValue = Number(r.final_value ?? r.current_value);
    if (!selected || !Number.isFinite(finalValue)) continue;
    const threshold = Number(selected.item?.threshold);
    if (!Number.isFinite(threshold)) continue;
    medianUsable++;
    if (finalValue > threshold) medianWins++;
  }
  return {
    signals: rows.length,
    threshold_stress_test: shiftStats,
    by_market: byMarket,
    bookmaker_odds_buckets: bucketSummary("bookmaker_odds"),
    model_odds_buckets: bucketSummary("model_fair_odds"),
    median_rule_v2: {
      signals: medianUsable,
      wins: medianWins,
      losses: medianUsable - medianWins,
      hit_rate: medianUsable ? Number((medianWins / medianUsable * 100).toFixed(2)) : 0
    },
    notes: {
      bookmaker_roi: "ROI calcul\xE9 uniquement quand bookmaker_odds contient une vraie cote externe.",
      model_odds: "Les buckets model_fair_odds mesurent la calibration du mod\xE8le, pas un ROI bookmaker r\xE9el.",
      legacy_median: "La r\xE8gle m\xE9diane exacte ne peut \xEAtre rejou\xE9e sur les anciens signaux qui ne stockaient pas leurs lignes candidates."
    }
  };
}
async function getLiveHeadroomBacktest(days = 90) {
  const boundedDays = Math.max(1, Math.min(365, Math.floor(days)));
  const since = new Date(Date.now() - boundedDays * 86400 * 1e3).toISOString();
  const { data, error } = await supabase.from("live_predictions").select("prediction_type, threshold, current_value, final_value, headroom, probability, reliability_score, live_odds, model_fair_odds, bookmaker_odds, odds_source, pricing_mode, signal_tier, line_candidate_count, line_candidate_rank, line_candidates, baseline_threshold, historical_uplift_cap, selected_uplift, model_version, outcome, validated, telegram_sent, created_at").eq("validated", true).eq("telegram_sent", true).gte("created_at", since).order("created_at", { ascending: false });
  if (error) {
    if (isUndefinedColumnError(error)) {
      return {
        period_days: boundedDays,
        since,
        migration_required: true,
        migration: "supabase/migrations/20261009000100_live_value_engine_v2.sql",
        error: error.message
      };
    }
    throw error;
  }
  return { period_days: boundedDays, since, migration_required: false, ...summarizeBacktestRows(data || []) };
}
function normalizeBsdStatsPayload(payload) {
  const raw = payload?.stats || {};
  const home = { ...raw?.home || {} };
  const away = { ...raw?.away || {} };
  const shotmap = Array.isArray(payload?.shotmap) ? payload.shotmap.filter((s) => String(s?.sit || "").toLowerCase() !== "shootout") : [];
  if (shotmap.length) {
    const homeShots = shotmap.filter((s) => s?.home === true);
    const awayShots = shotmap.filter((s) => s?.home === false);
    const onTarget = (s) => ["goal", "save"].includes(String(s?.type || "").toLowerCase());
    home.total_shots = homeShots.length;
    away.total_shots = awayShots.length;
    home.shots_on_target = homeShots.filter(onTarget).length;
    away.shots_on_target = awayShots.filter(onTarget).length;
  }
  return ensureLiveStatsShape({ home, away });
}
async function loadCachedLiveMatchRows(matchIds) {
  const ids = [...new Set(matchIds.map(String).filter(Boolean))];
  const map = /* @__PURE__ */ new Map();
  if (!ids.length) return map;
  const { data, error } = await supabase.from("matches_live").select("id, raw_data, updated_at").in("id", ids);
  if (error) {
    console.warn("Cache LIVE stats non lisible (ignor\xE9):", error.message);
    return map;
  }
  for (const row of data || []) map.set(String(row.id), row);
  return map;
}
async function reuseCachedStats(matches) {
  const cache2 = await loadCachedLiveMatchRows(
    (matches || []).map((m) => String(m?.id || ""))
  );
  return (matches || []).map((match) => {
    const row = cache2.get(String(match?.id));
    const cached = row?.raw_data || null;
    if (!cached) return match;
    const mergedStats = mergeLiveStats(
      cached?.live_stats || cached?.raw_data?.live_stats || {},
      getMatchLiveStats(match)
    );
    return {
      ...match,
      live_stats: mergedStats,
      stats_last_updated_at: match?.stats_last_updated_at || cached?.stats_last_updated_at || cached?.raw_data?.stats_last_updated_at || null,
      raw_data: {
        ...match?.raw_data || {},
        // Cache is a full normalized match; restore per-provider request timestamps.
        // These timestamps represent attempted requests, not observed statistics.
        bsd_detail_last_attempt_at: match?.raw_data?.bsd_detail_last_attempt_at || cached?.raw_data?.bsd_detail_last_attempt_at || null,
        sportscore_detail_last_attempt_at: match?.raw_data?.sportscore_detail_last_attempt_at || cached?.raw_data?.sportscore_detail_last_attempt_at || null,
        live_stats: mergedStats
      }
    };
  });
}
function isBsdNumericEvent(match) {
  return /^\d+$/.test(String(match?.id || ""));
}
function statsAgeSeconds(match) {
  const raw = match?.stats_last_updated_at || match?.raw_data?.stats_last_updated_at || null;
  if (!raw) return Number.POSITIVE_INFINITY;
  const ts = new Date(raw).getTime();
  if (!Number.isFinite(ts)) return Number.POSITIVE_INFINITY;
  return Math.max(0, Math.floor((Date.now() - ts) / 1e3));
}
async function enrichLiveMatchesWithApiFootballCache(matches) {
  const result = [...matches || []];
  const byCanonical = /* @__PURE__ */ new Map();
  for (let i = 0; i < result.length; i++) {
    const m = result[i];
    if (!m?.is_live || m?.is_finished) continue;
    const key = buildCanonicalMatchId(m);
    byCanonical.set(key, [...byCanonical.get(key) || [], i]);
  }
  const keys = [...byCanonical.keys()].slice(0, 400);
  if (!keys.length) return { matches: result, enriched: 0 };
  const since = new Date(Date.now() - 8 * 6e4).toISOString();
  const { data, error } = await supabase.from(T_STATS_SOURCES).select("canonical_match_id,source_match_id,home_team,away_team,event_date,minute,stats_json,updated_at,is_live").eq("source_name", "api_football").eq("is_live", true).gte("updated_at", since).in("canonical_match_id", keys).order("updated_at", { ascending: false }).limit(500);
  if (error) {
    console.warn("API_FOOTBALL_CACHE_UNAVAILABLE", error.message);
    return { matches: result, enriched: 0 };
  }
  let enriched = 0;
  for (const row of data || []) {
    const indexes = byCanonical.get(String(row.canonical_match_id)) || [];
    for (const index of indexes) {
      const match = result[index];
      const minute = safeNumber(match?.current_minute, 0);
      const extMinute = safeNumber(row?.minute, 0);
      if (minute < 8 || extMinute < 8 || Math.abs(minute - extMinute) > 8) continue;
      if (sameMatchScore(match, row) < 0.9) continue;
      const external = ensureLiveStatsShape(row.stats_json || {});
      if (statsCompleteness(external).core_complete <= 0) continue;
      const merged = mergeLiveStats(getMatchLiveStats(match), external);
      const raw = match.raw_data || {};
      const currentAt = Date.parse(match?.stats_last_updated_at || "");
      const externalAt = Date.parse(row.updated_at || "");
      const latestTime = Number.isFinite(currentAt) && currentAt > externalAt ? match.stats_last_updated_at : row.updated_at;
      result[index] = {
        ...match,
        live_stats: merged,
        stats_last_updated_at: latestTime,
        raw_data: {
          ...raw,
          live_stats: merged,
          stats_sources: [.../* @__PURE__ */ new Set([...raw.stats_sources || [], "api_football"])],
          provider_refs: {
            ...raw.provider_refs || {},
            api_football: { id: String(row.source_match_id), quality: 95, stats_updated_at: row.updated_at }
          },
          merge_meta: {
            ...raw.merge_meta || {},
            sources: [.../* @__PURE__ */ new Set([...raw.merge_meta?.sources || [], "api_football"])],
            confidence_score: Math.max(safeNumber(raw.merge_meta?.confidence_score, 0), 85)
          }
        }
      };
      enriched++;
    }
  }
  return { matches: result, enriched };
}
async function enrichLiveMatchesWithBsdStats(matches) {
  const budget = bsdStatsCallBudget();
  if (budget <= 0) {
    return {
      matches,
      calls: 0,
      enriched: 0,
      failed: 0,
      skipped_quota: true
    };
  }
  const candidates = (matches || []).filter((m) => {
    if (!isBsdNumericEvent(m)) return false;
    const lastAttempt = Date.parse(String(m?.raw_data?.bsd_detail_last_attempt_at || ""));
    if (Number.isFinite(lastAttempt) && Date.now() - lastAttempt < BSD_STATS_REFRESH_SECONDS * 1e3) return false;
    const minute = safeNumber(m?.current_minute ?? m?.minute, 0);
    if (minute < 10 || minute > 88) return false;
    const completeness = statsCompleteness(getMatchLiveStats(m));
    return completeness.core_complete < 3 || statsAgeSeconds(m) >= BSD_STATS_REFRESH_SECONDS;
  }).sort((a, b2) => {
    const ca = statsCompleteness(getMatchLiveStats(a)).core_complete;
    const cb = statsCompleteness(getMatchLiveStats(b2)).core_complete;
    if (ca !== cb) return ca - cb;
    return statsAgeSeconds(b2) - statsAgeSeconds(a);
  });
  const rotation = candidates.length ? Math.floor(Date.now() / 6e4) * Math.max(1, budget) % candidates.length : 0;
  const scheduledCandidates = [...candidates.slice(rotation), ...candidates.slice(0, rotation)].slice(0, budget);
  let calls = 0;
  let enriched = 0;
  let failed = 0;
  const out = [...matches || []];
  const indexById = new Map(out.map((m, i) => [String(m?.id), i]));
  for (const match of scheduledCandidates) {
    const idx = indexById.get(String(match.id));
    if (idx == null) continue;
    out[idx] = { ...out[idx], raw_data: {
      ...out[idx]?.raw_data || {},
      bsd_detail_last_attempt_at: nowIso()
    } };
    try {
      calls++;
      const payload = await fetchBSD(`/events/${match.id}/stats/`);
      const freshStats = normalizeBsdStatsPayload(payload);
      const hasObservedStats = ["home", "away"].some((side) => Object.values(freshStats?.[side] || {}).some((v) => nullableNumber(v) != null));
      if (!hasObservedStats) continue;
      const mergedStats = mergeLiveStats(getMatchLiveStats(match), freshStats, true);
      out[idx] = {
        ...out[idx],
        live_stats: mergedStats,
        stats_last_updated_at: nowIso(),
        raw_data: {
          ...out[idx]?.raw_data || {},
          live_stats: mergedStats,
          stats_last_updated_at: nowIso(),
          stats_sources: [
            .../* @__PURE__ */ new Set([
              ...out[idx]?.raw_data?.stats_sources || [],
              "bsd_stats"
            ])
          ],
          stats_authority: "bsd_stats",
          bsd_detail_observed_stats: freshStats,
          // A later
          // provider cannot overwrite its complete observed market pairs.
          bsd_primary_stats: mergeLiveStats(
            out[idx]?.raw_data?.bsd_primary_stats || {},
            freshStats,
            true
          ),
          stats_corrected_at: nowIso()
        }
      };
      enriched++;
    } catch (e) {
      failed++;
      if (isBSDQuotaError(e)) {
        console.warn("\u26A0\uFE0F Quota BSD atteint pendant enrichissement stats; arr\xEAt des appels stats.");
        break;
      }
      console.warn("\u26A0\uFE0F Stats BSD indisponibles pour le match", {
        match_id: match?.id,
        error: e?.message || String(e)
      });
    }
  }
  return {
    matches: out,
    calls,
    enriched,
    failed,
    skipped_quota: false
  };
}
function stableRefreshMatchId(match) {
  return String(match?.id ?? buildCanonicalMatchId(match));
}
function sortMatchesForRefresh(matches) {
  return [...matches || []].sort(
    (a, b2) => stableRefreshMatchId(a).localeCompare(stableRefreshMatchId(b2))
  );
}
async function loadRecentRefreshSnapshot(maxAgeSeconds = 150) {
  const since = new Date(Date.now() - maxAgeSeconds * 1e3).toISOString();
  const { data, error } = await supabase.from(T_STATS_MERGED).select("merged_match_json, updated_at").gte("updated_at", since).order("updated_at", { ascending: false }).limit(500);
  if (error || !data?.length) return [];
  const newest = Math.max(
    ...data.map((r) => new Date(r.updated_at).getTime()).filter(Number.isFinite)
  );
  const recent = data.filter((r) => {
    const ts = new Date(r.updated_at).getTime();
    return Number.isFinite(ts) && newest - ts <= 15e3;
  });
  const byId = /* @__PURE__ */ new Map();
  for (const r of recent) {
    const m = r?.merged_match_json;
    if (!m) continue;
    if (m?.is_finished === true) continue;
    const id = stableRefreshMatchId(m);
    if (!byId.has(id)) byId.set(id, m);
  }
  return sortMatchesForRefresh([...byId.values()]);
}
async function syncUpcomingFixtures() {
  const { data: recent } = await supabase.from("live_scheduled_fixtures").select("updated_at").order("updated_at", { ascending: false }).limit(1);
  if (recent?.[0]?.updated_at && Date.now() - Date.parse(recent[0].updated_at) < 55e3) {
    return { throttled: true };
  }
  const dates = [0, 1].map((days) => {
    const d = new Date(Date.now() + days * 864e5);
    return d.toISOString().slice(0, 10);
  });
  const feed = [];
  const failures2 = [];
  for (const day of dates) {
    const { data: cached } = await supabase.from("espn_feed_cache").select("payload").eq("cache_key", "scoreboard:" + toDateKey(day)).maybeSingle();
    for (const event of cached?.payload?.events || []) {
      const match = normalizeEspnEventToOriginalMatch(event);
      if (match) feed.push({ source: "espn", match });
    }
  }
  const requested = await Promise.allSettled(dates.flatMap((day) => [
    fetchSportScoreFixtures(day),
    fetchTheSportsDbDay(day),
    fetchOpenLigaDay(day)
  ]));
  for (let i = 0; i < requested.length; i++) {
    const result = requested[i];
    const source = ["sportscore", "thesportsdb", "openligadb"][i % 3];
    if (result.status === "fulfilled") {
      for (const match of result.value || []) feed.push({ source, match });
    } else failures2.push(source + ": " + String(result.reason).slice(0, 100));
  }
  const unique = [];
  const lower = Date.now() - 10 * 6e4;
  const upper = Date.now() + 48 * 36e5;
  const rank = { api_original: 0, espn: 1, api_football: 2, sportscore: 3, thesportsdb: 4, openligadb: 5 };
  for (const entry of feed) {
    const match = entry.match;
    const kickoff = Date.parse(String(getMatchEventDate(match) || ""));
    if (!Number.isFinite(kickoff) || kickoff < lower || kickoff > upper || match.is_live || match.is_finished) continue;
    const found = unique.find((x) => sameMatchScore(x.match, match) >= 0.85);
    if (found) {
      if (!found.sources.includes(entry.source)) found.sources.push(entry.source);
      if (rank[entry.source] < rank[found.source]) {
        const inherited = found.match;
        found.match = {
          ...match,
          home_logo: match.home_logo || inherited.home_logo,
          away_logo: match.away_logo || inherited.away_logo
        };
        found.source = entry.source;
      } else {
        found.match.home_logo ||= match.home_logo || null;
        found.match.away_logo ||= match.away_logo || null;
      }
    } else unique.push({ ...entry, sources: [entry.source] });
  }
  const rows = unique.slice(0, 500).map(({ match, source, sources }) => ({
    fixture_id: String(match.id || source + ":" + buildCanonicalMatchId(match)),
    event_date: getMatchEventDate(match),
    home_team: String(match.home_team || ""),
    away_team: String(match.away_team || ""),
    source_names: sources,
    fixture: { ...match, source_names: sources, source },
    updated_at: nowIso()
  }));
  if (rows.length) {
    const { error } = await supabase.from("live_scheduled_fixtures").upsert(rows, { onConflict: "fixture_id" });
    if (error) throw error;
  }
  console.info("SCHEDULED_MULTI_SOURCE", { count: rows.length, failures: failures2 });
  return { count: rows.length, failures: failures2 };
}
async function pulseAllLiveFixtures(matches) {
  const rows = matches.filter((m) => m?.is_live && !m?.is_finished).slice(0, 500).map((m) => ({
    id: String(m.id || ""),
    home_team: String(m.home_team || ""),
    away_team: String(m.away_team || ""),
    home_score: nullableNumber(m.home_score),
    away_score: nullableNumber(m.away_score),
    current_minute: nullableNumber(m.current_minute) || null,
    league_name: String(m.league_name || m.league?.name || ""),
    status: String(m.status || "live"),
    event_date: getMatchEventDate(m)
  }));
  if (!rows.length) return;
  const { error } = await supabase.rpc("upsert_live_fixture_status", { p_rows: rows });
  if (error) console.warn("LIVE_FIXTURE_PULSE_FAILED", error.message);
}
async function refreshLiveDataBatch(options = {}) {
  const batchSize = Math.max(
    1,
    Math.min(5, Math.floor(options.batchSize ?? LIVE_REFRESH_BATCH_SIZE))
  );
  const cursor = String(options.cursor || "");
  const allowTelegram = TELEGRAM_IN_REFRESH && options.allowTelegram !== false;
  const refreshAt = nowIso();
  let allRawMatches = [];
  let sourceRows = [];
  let sourceMeta = {
    original_source_matches: 0,
    espn_source_matches: 0,
    duplicates_merged: 0,
    espn_only_matches: 0,
    espn_enabled: ENABLE_ESPN_MERGE
  };
  let espnError = null;
  let bsdError = null;
  let bsdRateLimited = false;
  let snapshotReused = false;
  let coverage = null;
  if (options.useSnapshot) {
    allRawMatches = await loadRecentRefreshSnapshot();
    snapshotReused = allRawMatches.length > 0;
  }
  if (!snapshotReused) {
    let originalRawMatches = [];
    coverage = await fetchBSDCoverage();
    const liveNow = safeNumber(coverage?.live_now, -1);
    const [espnResult, freeProviderData] = await Promise.all([
      fetchEspnLiveMatchesForMerge(),
      collectFreeLiveProviders()
    ]);
    espnError = espnResult.error;
    const sportscoreRows = freeProviderData?.sportscore || [];
    const tsdbRows = freeProviderData?.thesportsdb || [];
    const openligaRows = freeProviderData?.openligadb || [];
    const regionalEspnResult = await fetchRegionalEspnLiveMatchesForMerge([
      ...sportscoreRows,
      ...tsdbRows,
      ...openligaRows
    ]);
    const espnCombinedById = /* @__PURE__ */ new Map();
    for (const match of [...espnResult.matches || [], ...regionalEspnResult.matches]) {
      const key = String(match?.source_match_id || match?.id || "");
      if (key) espnCombinedById.set(key, match);
    }
    espnResult.matches = [...espnCombinedById.values()];
    if (regionalEspnResult.errors.length) console.warn("ESPN_REGIONAL_ERRORS", regionalEspnResult.errors);
    console.info("ESPN_REGIONAL_LIVE_COVERAGE", {
      checked_leagues: regionalEspnResult.leagues,
      checked_dates: espnLiveScoreboardDates(),
      regional_matches: regionalEspnResult.matches.length,
      combined_matches: espnResult.matches.length
    });
    const freeShowsLive = [
      ...espnResult.matches || [],
      ...sportscoreRows,
      ...tsdbRows,
      ...openligaRows
    ].some((m) => m?.is_live === true);
    const periodicBsdProbe = Math.floor(Date.now() / 6e4) % 5 === 0;
    const skipBsdLive = options.skipBsd === true || liveNow === 0 && !freeShowsLive && !periodicBsdProbe;
    if (!skipBsdLive) {
      try {
        const liveData = await fetchBSD("/events/live/");
        originalRawMatches = bsdResults(liveData);
      } catch (e) {
        bsdError = e?.message || String(e);
        bsdRateLimited = isBSDQuotaError(e);
        if (bsdRateLimited) {
          console.warn("\u26A0\uFE0F Quota BSD \xE9puis\xE9: sources gratuites + cache prennent le relais");
        } else {
          console.error("\u26A0\uFE0F BSD v2 live indisponible: sources gratuites prennent le relais", e);
        }
      }
    }
    const incomingEspnIds = (espnResult.matches || []).map((m) => String(m?.source_match_id || m?.raw_data?.event_id || "")).filter(Boolean);
    const knownProviderMappings = /* @__PURE__ */ new Map();
    if (incomingEspnIds.length) {
      const { data: mappingRows, error: mapReadError } = await supabase.from("espn_match_map").select("espn_id,primary_match_id").in("espn_id", [...new Set(incomingEspnIds)].slice(0, 500));
      if (!mapReadError) {
        for (const row of mappingRows || []) {
          knownProviderMappings.set(String(row.espn_id), String(row.primary_match_id));
        }
      } else {
        console.warn("ESPN provider mappings unavailable; using strict fixture matching", mapReadError);
      }
    }
    const merged = mergeOriginalAndEspnMatches(
      originalRawMatches,
      espnResult.matches || [],
      knownProviderMappings
    );
    if (merged.providerMappings?.length) {
      const { error: mapWriteError } = await supabase.from("espn_match_map").upsert(merged.providerMappings, { onConflict: "espn_id" });
      if (mapWriteError) console.warn("ESPN provider mapping persistence failed", mapWriteError);
    }
    let providerMerged = merged.mergedMatches;
    sourceRows = [...merged.sourceRows || []];
    const providerMeta = {};
    for (const [providerName, rows] of [
      ["sportscore", sportscoreRows],
      ["thesportsdb", tsdbRows],
      ["openligadb", openligaRows]
    ]) {
      const result = mergeAdditionalProviderMatches(
        providerMerged,
        rows,
        providerName
      );
      providerMerged = result.matches;
      sourceRows.push(...result.sourceRows);
      providerMeta[providerName + "_source_matches"] = rows.length;
      providerMeta[providerName + "_merged"] = result.merged;
      providerMeta[providerName + "_only_live"] = result.providerOnly;
    }
    allRawMatches = sortMatchesForRefresh(providerMerged);
    await pulseAllLiveFixtures(allRawMatches);
    sourceMeta = {
      ...merged.meta || sourceMeta,
      ...providerMeta,
      bsd_live_call_saved: skipBsdLive,
      free_provider_errors: freeProviderData?.errors || {}
    };
    allRawMatches = await reuseCachedStats(allRawMatches);
    const espnSummaryEnrichment = await enrichLiveMatchesWithEspnSummaries(allRawMatches);
    allRawMatches = sortMatchesForRefresh(espnSummaryEnrichment.matches);
    const movioddsStatsEnrichment = await enrichLiveMatchesWithMoviOddsStats(allRawMatches);
    allRawMatches = sortMatchesForRefresh(movioddsStatsEnrichment.matches);
    sourceRows.push(...movioddsStatsEnrichment.sourceRows);
    const statsEnrichment = await enrichLiveMatchesWithBsdStats(allRawMatches);
    allRawMatches = sortMatchesForRefresh(statsEnrichment.matches);
    const apiFootballCache = await enrichLiveMatchesWithApiFootballCache(allRawMatches);
    allRawMatches = sortMatchesForRefresh(apiFootballCache.matches);
    const freeStatsEnrichment = await enrichLiveMatchesWithFreeStats(allRawMatches);
    allRawMatches = sortMatchesForRefresh(freeStatsEnrichment.matches);
    sourceMeta = {
      ...sourceMeta,
      api_football_stats_enriched: apiFootballCache.enriched,
      espn_summary_stats_calls: espnSummaryEnrichment.calls,
      espn_summary_stats_enriched: espnSummaryEnrichment.enriched,
      espn_summary_stats_pairs_gained: espnSummaryEnrichment.complete_pairs_gained,
      moviodds_stats_observations: movioddsStatsEnrichment.observations,
      moviodds_stats_enriched: movioddsStatsEnrichment.enriched,
      free_stats_calls: freeStatsEnrichment.calls,
      free_stats_enriched: freeStatsEnrichment.enriched,
      sportscore_stats_calls: freeStatsEnrichment.sportscore_calls,
      thesportsdb_resolve_calls: freeStatsEnrichment.thesportsdb_resolve_calls,
      thesportsdb_stats_calls: freeStatsEnrichment.thesportsdb_calls,
      sportscore_odds_sections_detected: freeStatsEnrichment.odds_sections_detected,
      bsd_stats_calls: statsEnrichment.calls,
      bsd_stats_enriched: statsEnrichment.enriched,
      bsd_stats_failed: statsEnrichment.failed,
      bsd_stats_skipped_quota: statsEnrichment.skipped_quota,
      bsd_stats_calls_saved_estimate: Math.max(
        0,
        freeStatsEnrichment.enriched
      ),
      bsd_quota_remaining: bsdQuotaRemaining,
      bsd_quota_reset_seconds: bsdQuotaResetSeconds
    };
    allRawMatches = allRawMatches.map((match) => {
      const raw = match?.raw_data || {};
      const bsd = raw.bsd_primary_stats;
      const espn = raw.espn_primary_stats;
      let stats = getMatchLiveStats(match);
      if (bsd) stats = preserveBsdCoreMarketPairs(bsd, stats);
      if (espn) stats = preferObservedCoreMarketPairs(espn, stats);
      stats = ensureLiveStatsShape(stats);
      const priority = espn && statsCompleteness(espn).core_complete > 0 ? "espn" : bsd && statsCompleteness(bsd).core_complete > 0 ? "bsd" : raw?.stats_authority || raw?.merge_meta?.primary_source || null;
      return { ...match, live_stats: stats, raw_data: { ...raw, live_stats: stats, stats_primary_source: priority } };
    });
    const bsdDetailById = /* @__PURE__ */ new Map();
    for (const match of allRawMatches) {
      const detail = match?.raw_data?.bsd_detail_observed_stats;
      if (!detail || !/^\d+$/.test(String(match?.id || ""))) continue;
      bsdDetailById.set(String(match.id), {
        stats: ensureLiveStatsShape(detail),
        minute: safeNumber(match.current_minute, 0)
      });
    }
    if (bsdDetailById.size) sourceRows = sourceRows.map((row) => {
      if (row.source_name !== "api_original") return row;
      const observed = bsdDetailById.get(String(row.source_match_id));
      if (!observed) return row;
      return {
        ...row,
        minute: Math.max(safeNumber(row.minute, 0), observed.minute),
        stats_json: observed.stats,
        raw_json: {
          ...row.raw_json || {},
          live_stats: observed.stats,
          stats_authority: "bsd_stats",
          stats_last_updated_at: nowIso()
        }
      };
    });
    const espnDetailed = /* @__PURE__ */ new Map();
    for (const match of allRawMatches) {
      const observed = match?.raw_data?.espn_summary_observed_stats;
      const eventId = String(match?.raw_data?.espn_summary_event_id || "");
      if (!observed || !eventId) continue;
      espnDetailed.set(eventId, {
        stats: ensureLiveStatsShape(observed),
        minute: safeNumber(match?.current_minute, 0)
      });
    }
    if (espnDetailed.size) sourceRows = sourceRows.map((row) => {
      if (row.source_name !== "espn") return row;
      const id = String(row.source_match_id || "").replace(/^espn:/, "");
      const observed = espnDetailed.get(id);
      if (!observed) return row;
      return {
        ...row,
        minute: Math.max(safeNumber(row.minute, 0), observed.minute),
        stats_json: observed.stats,
        raw_json: {
          ...row.raw_json || {},
          live_stats: observed.stats,
          stats_authority: "espn_summary",
          stats_last_updated_at: nowIso()
        }
      };
    });
    const sportScoreDetailById = /* @__PURE__ */ new Map();
    for (const match of allRawMatches) {
      const detailStats = match?.raw_data?.sportscore_detail_observed_stats;
      if (!detailStats || typeof detailStats !== "object") continue;
      const rawId = String(
        match?.raw_data?.provider_refs?.sportscore?.id || (String(match?.id || "").startsWith("sportscore:") ? match.id : "")
      ).replace(/^sportscore:/, "");
      if (!rawId) continue;
      sportScoreDetailById.set("sportscore:" + rawId, {
        stats: ensureLiveStatsShape(detailStats),
        minute: safeNumber(match?.current_minute, 0)
      });
    }
    if (sportScoreDetailById.size) {
      sourceRows = sourceRows.map((row) => {
        if (row.source_name !== "sportscore") return row;
        const detailed = sportScoreDetailById.get(String(row.source_match_id));
        if (!detailed) return row;
        const minute = Math.max(safeNumber(row.minute, 0), detailed.minute);
        return {
          ...row,
          minute,
          stats_json: detailed.stats,
          raw_json: {
            ...row.raw_json || {},
            current_minute: minute,
            live_stats: detailed.stats,
            stats_last_updated_at: nowIso(),
            stats_authority: "sportscore_stats"
          }
        };
      });
    }
    const liveCoverage = {
      total: allRawMatches.length,
      bsd_primary: 0,
      corners: 0,
      total_shots: 0,
      fouls: 0,
      all_three: 0,
      api_football_enriched: safeNumber(sourceMeta.api_football_stats_enriched, 0),
      espn_summary_pairs_gained: safeNumber(sourceMeta.espn_summary_stats_pairs_gained, 0),
      bsd_stats_calls: safeNumber(sourceMeta.bsd_stats_calls, 0)
    };
    for (const match of allRawMatches) {
      const completeness = statsCompleteness(getMatchLiveStats(match));
      if (match?.raw_data?.bsd_primary_stats) liveCoverage.bsd_primary++;
      if (completeness.corners) liveCoverage.corners++;
      if (completeness.shots) liveCoverage.total_shots++;
      if (completeness.fouls) liveCoverage.fouls++;
      if (completeness.core_complete === 3) liveCoverage.all_three++;
    }
    console.info("LIVE_MARKET_COVERAGE", liveCoverage);
    if (allRawMatches.length) {
      await persistStatsSourcesAndMerged(sourceRows, allRawMatches);
    }
  }
  allRawMatches.sort(
    (a, b2) => stableRefreshMatchId(a).localeCompare(stableRefreshMatchId(b2))
  );
  const candidates = cursor ? allRawMatches.filter(
    (m) => stableRefreshMatchId(m).localeCompare(cursor) > 0
  ) : allRawMatches;
  const rawMatches = candidates.slice(0, batchSize);
  const nextCursor = rawMatches.length ? stableRefreshMatchId(rawMatches[rawMatches.length - 1]) : cursor || null;
  const hasMore = candidates.length > rawMatches.length;
  if (!rawMatches.length) {
    return {
      matches: [],
      has_more: false,
      next_cursor: nextCursor,
      meta: {
        total_live_matches: allRawMatches.length,
        batch_size: batchSize,
        batch_count: 0,
        cursor: cursor || null,
        next_cursor: nextCursor,
        original_source_matches: safeNumber(sourceMeta.original_source_matches, 0),
        espn_source_matches: safeNumber(sourceMeta.espn_source_matches, 0),
        sportscore_source_matches: safeNumber(sourceMeta.sportscore_source_matches, 0),
        thesportsdb_source_matches: safeNumber(sourceMeta.thesportsdb_source_matches, 0),
        openligadb_source_matches: safeNumber(sourceMeta.openligadb_source_matches, 0),
        sportscore_merged: safeNumber(sourceMeta.sportscore_merged, 0),
        thesportsdb_merged: safeNumber(sourceMeta.thesportsdb_merged, 0),
        openligadb_merged: safeNumber(sourceMeta.openligadb_merged, 0),
        api_football_stats_enriched: safeNumber(sourceMeta.api_football_stats_enriched, 0),
        espn_summary_stats_calls: safeNumber(sourceMeta.espn_summary_stats_calls, 0),
        espn_summary_stats_enriched: safeNumber(sourceMeta.espn_summary_stats_enriched, 0),
        espn_summary_stats_pairs_gained: safeNumber(sourceMeta.espn_summary_stats_pairs_gained, 0),
        free_stats_calls: safeNumber(sourceMeta.free_stats_calls, 0),
        free_stats_enriched: safeNumber(sourceMeta.free_stats_enriched, 0),
        sportscore_stats_calls: safeNumber(sourceMeta.sportscore_stats_calls, 0),
        thesportsdb_stats_calls: safeNumber(sourceMeta.thesportsdb_stats_calls, 0),
        bsd_live_call_saved: Boolean(sourceMeta.bsd_live_call_saved),
        bsd_stats_calls_saved_estimate: safeNumber(sourceMeta.bsd_stats_calls_saved_estimate, 0),
        sportscore_odds_sections_detected: safeNumber(sourceMeta.sportscore_odds_sections_detected, 0),
        bsd_stats_calls: safeNumber(sourceMeta.bsd_stats_calls, 0),
        bsd_stats_enriched: safeNumber(sourceMeta.bsd_stats_enriched, 0),
        bsd_stats_failed: safeNumber(sourceMeta.bsd_stats_failed, 0),
        bsd_quota_remaining: sourceMeta.bsd_quota_remaining ?? bsdQuotaRemaining,
        duplicates_merged: safeNumber(sourceMeta.duplicates_merged, 0),
        espn_only_matches: safeNumber(sourceMeta.espn_only_matches, 0),
        espn_enabled: ENABLE_ESPN_MERGE,
        espn_error: espnError,
        bsd_error: bsdError,
        bsd_rate_limited: bsdRateLimited,
        bsd_skipped: options.skipBsd === true || safeNumber(coverage?.live_now, -1) === 0,
        snapshot_reused: snapshotReused,
        telegram_in_refresh: allowTelegram,
        predictions_created: 0,
        predictions_existing: 0,
        predictions_failed: 0
      }
    };
  }
  const normalizedMatches = rawMatches.map(
    (m) => normalizeMatch(m, refreshAt)
  );
  const emptyMarketAudit = () => ({
    missing_stats: 0,
    missing_minute: 0,
    out_of_window: 0,
    below_minimum: 0,
    with_stats: 0,
    preflight: 0,
    model_rejected: 0,
    model_candidates: 0,
    quality_rejected: 0,
    signals: 0
  });
  const marketAudit = {
    shots: emptyMarketAudit(),
    corners: emptyMarketAudit(),
    fouls: emptyMarketAudit()
  };
  const categories = [
    { name: "shots", stat: "total_shots", prediction: "total_shots", min: 6, earliest: 15, latest: 83 },
    { name: "corners", stat: "corner_kicks", prediction: "total_corners", min: 3, earliest: 18, latest: 82 },
    { name: "fouls", stat: "fouls", prediction: "total_fouls", min: 6, earliest: 18, latest: 84 }
  ];
  for (const m of normalizedMatches) {
    const minute = safeNumber(m.current_minute, 0);
    for (const cat of categories) {
      const gate = marketAudit[cat.name];
      if (!hasCompleteStatPair(m.live_stats, cat.stat)) {
        gate.missing_stats++;
        continue;
      }
      gate.with_stats++;
      const total = statPairTotal(
        m.live_stats,
        cat.stat,
        cat.name === "corners" ? "corners" : cat.stat
      );
      const eligibleMinute = minute >= cat.earliest && minute <= cat.latest;
      const eligibleTotal = Number.isFinite(total) && total >= cat.min;
      if (minute <= 0) gate.missing_minute++;
      else if (!eligibleMinute) gate.out_of_window++;
      else if (!eligibleTotal) gate.below_minimum++;
      else gate.preflight++;
      const modelCandidate = (m.all_predictions || []).some((p) => p.type === cat.prediction);
      const publishable = (m.predictions || []).some((p) => p.type === cat.prediction);
      if (modelCandidate) gate.model_candidates++;
      else if (eligibleMinute && eligibleTotal) gate.model_rejected++;
      if (publishable) gate.signals++;
      else if (modelCandidate) gate.quality_rejected++;
    }
  }
  console.info("LIVE_MARKET_GATE_AUDIT", {
    batch_matches: normalizedMatches.length,
    markets: marketAudit
  });
  await cacheLiveMatches(rawMatches, refreshAt);
  let createdPreds = 0;
  let existingPreds = 0;
  let failedPreds = 0;
  const freshTelegramIds = [];
  for (const m of normalizedMatches) {
    for (const pred of m.predictions || []) {
      try {
        const res = await savePrediction(m, pred, { sendTelegram: false });
        if (res.created) {
          createdPreds++;
          if (res.id) freshTelegramIds.push(String(res.id));
        } else existingPreds++;
      } catch (e) {
        failedPreds++;
        console.error("savePrediction failed (ignored):", e);
      }
    }
  }
  const noTelegram = () => ({ telegram_retry_enabled: true, telegram_retry_processed: 0, telegram_retry_sent: 0, telegram_retry_failed: 0, telegram_retry_skipped: 0 });
  let telegramRetry = noTelegram();
  if (allowTelegram) {
    try {
      telegramRetry = freshTelegramIds.length ? await processTelegramPredictionById(freshTelegramIds[0]) : await retryPendingTelegramLiveCoupons(normalizedMatches, 1);
    } catch (e) {
      console.error("Nouvelle publication Telegram prioritaire \xE9chou\xE9e:", e);
      telegramRetry = { ...noTelegram(), telegram_retry_failed: 1 };
    }
  }
  const imageBudgetRemaining = allowTelegram && telegramRetry.telegram_retry_processed === 0;
  const instant = await validatePredictionsInPlay(normalizedMatches, {
    maxInstantValidations: imageBudgetRemaining ? 1 : 0,
    sendTelegram: imageBudgetRemaining
  });
  return {
    matches: normalizedMatches,
    has_more: hasMore,
    next_cursor: nextCursor,
    meta: {
      total_live_matches: allRawMatches.length,
      matches_live: rawMatches.length,
      batch_size: batchSize,
      batch_count: rawMatches.length,
      cursor: cursor || null,
      next_cursor: nextCursor,
      has_more: hasMore,
      original_source_matches: safeNumber(sourceMeta.original_source_matches, 0),
      espn_source_matches: safeNumber(sourceMeta.espn_source_matches, 0),
      sportscore_source_matches: safeNumber(sourceMeta.sportscore_source_matches, 0),
      thesportsdb_source_matches: safeNumber(sourceMeta.thesportsdb_source_matches, 0),
      openligadb_source_matches: safeNumber(sourceMeta.openligadb_source_matches, 0),
      sportscore_merged: safeNumber(sourceMeta.sportscore_merged, 0),
      thesportsdb_merged: safeNumber(sourceMeta.thesportsdb_merged, 0),
      openligadb_merged: safeNumber(sourceMeta.openligadb_merged, 0),
      free_stats_calls: safeNumber(sourceMeta.free_stats_calls, 0),
      free_stats_enriched: safeNumber(sourceMeta.free_stats_enriched, 0),
      sportscore_stats_calls: safeNumber(sourceMeta.sportscore_stats_calls, 0),
      thesportsdb_stats_calls: safeNumber(sourceMeta.thesportsdb_stats_calls, 0),
      bsd_live_call_saved: Boolean(sourceMeta.bsd_live_call_saved),
      bsd_stats_calls_saved_estimate: safeNumber(sourceMeta.bsd_stats_calls_saved_estimate, 0),
      sportscore_odds_sections_detected: safeNumber(sourceMeta.sportscore_odds_sections_detected, 0),
      bsd_stats_calls: safeNumber(sourceMeta.bsd_stats_calls, 0),
      bsd_stats_enriched: safeNumber(sourceMeta.bsd_stats_enriched, 0),
      bsd_stats_failed: safeNumber(sourceMeta.bsd_stats_failed, 0),
      bsd_quota_remaining: sourceMeta.bsd_quota_remaining ?? bsdQuotaRemaining,
      duplicates_merged: safeNumber(sourceMeta.duplicates_merged, 0),
      espn_only_matches: safeNumber(sourceMeta.espn_only_matches, 0),
      espn_enabled: ENABLE_ESPN_MERGE,
      espn_error: espnError,
      bsd_error: bsdError,
      bsd_rate_limited: bsdRateLimited,
      bsd_skipped: options.skipBsd === true || safeNumber(coverage?.live_now, -1) === 0,
      snapshot_reused: snapshotReused,
      market_diagnostics: marketAudit,
      matches_missing_minute: normalizedMatches.filter((m) => safeNumber(m?.current_minute, 0) <= 0).length,
      telegram_in_refresh: allowTelegram,
      predictions_created: createdPreds,
      predictions_existing: existingPreds,
      predictions_failed: failedPreds,
      ...telegramRetry,
      ...instant
    }
  };
}
async function invokeRefreshBatch(cursor, batchSize, allowTelegram = true, skipBsd = false, useSnapshot = false) {
  const endpoint = new URL(
    `${SUPABASE_URL.replace(/\/$/, "")}/functions/v1/live/refresh/batch`
  );
  endpoint.searchParams.set("batch_size", String(batchSize));
  endpoint.searchParams.set("allow_telegram", allowTelegram ? "1" : "0");
  endpoint.searchParams.set("skip_bsd", skipBsd ? "1" : "0");
  endpoint.searchParams.set("use_snapshot", useSnapshot ? "1" : "0");
  if (cursor) endpoint.searchParams.set("cursor", cursor);
  const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
    "apikey": SUPABASE_SERVICE_ROLE_KEY
  };
  if (CRON_SECRET) headers["x-cron-secret"] = CRON_SECRET;
  const res = await fetch(endpoint.toString(), {
    method: "POST",
    headers
  });
  const rawBody = await res.text().catch(() => "");
  let body = {};
  try {
    body = rawBody ? JSON.parse(rawBody) : {};
  } catch {
    body = { raw: rawBody };
  }
  if (!res.ok) {
    const err = new Error(
      `refresh batch HTTP ${res.status}: ${body?.message || body?.error || rawBody || res.statusText}`
    );
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}
async function refreshLiveDataInBatches(batchSize = LIVE_REFRESH_BATCH_SIZE, lockOwner = null) {
  const { data: progress, error: progressError } = await supabase.from("live_refresh_control").select("cursor, updated_at").eq("key", "live_refresh").maybeSingle();
  if (progressError) throw progressError;
  const progressAt = Date.parse(String(progress?.updated_at || ""));
  let cursor = progress?.cursor && Number.isFinite(progressAt) && Date.now() - progressAt < 30 * 6e4 ? String(progress.cursor) : null;
  let batchNumber = 0;
  let processedMatches = 0;
  let hasMore = true;
  let lastTotalLiveMatches = 0;
  let skipBsd = false;
  const aggregate = {
    batches_completed: 0,
    predictions_created: 0,
    predictions_existing: 0,
    predictions_failed: 0,
    telegram_retry_processed: 0,
    telegram_retry_sent: 0,
    telegram_retry_failed: 0,
    instant_validated: 0,
    instant_validation_deferred: 0,
    updated_running: 0,
    bsd_skipped_batches: 0,
    bsd_stats_calls: 0,
    bsd_stats_enriched: 0,
    api_football_stats_enriched: 0,
    espn_summary_stats_pairs_gained: 0,
    matches_missing_minute: 0,
    market_diagnostics: {
      shots: {},
      corners: {},
      fouls: {}
    }
  };
  while (hasMore && batchNumber < LIVE_REFRESH_MAX_BATCHES) {
    if (lockOwner) {
      const { data: renewed, error: renewError } = await supabase.rpc("renew_live_refresh", { p_owner: lockOwner });
      if (renewError || !renewed) throw new Error("Live refresh lease lost; aborting stale coordinator");
    }
    let effectiveBatchSize = Math.max(1, Math.min(5, batchSize));
    let allowTelegram = true;
    let result = null;
    while (!result) {
      try {
        result = await invokeRefreshBatch(
          cursor,
          effectiveBatchSize,
          allowTelegram,
          skipBsd,
          batchNumber > 0
        );
      } catch (e) {
        if (safeNumber(e?.status, 0) === 546 && effectiveBatchSize > 1) {
          const previousSize = effectiveBatchSize;
          effectiveBatchSize = Math.max(1, Math.floor(effectiveBatchSize / 2));
          console.warn(
            `\u26A0\uFE0F CPU 546 sur lot ${previousSize}; retry avec ${effectiveBatchSize} match(s)`
          );
          continue;
        }
        if (safeNumber(e?.status, 0) === 546 && effectiveBatchSize === 1 && allowTelegram) {
          allowTelegram = false;
          console.warn(
            "\u26A0\uFE0F CPU 546 m\xEAme avec 1 match; retry du lot sans rendu Telegram"
          );
          continue;
        }
        throw e;
      }
    }
    const meta = result?.meta || {};
    if (meta.bsd_rate_limited) skipBsd = true;
    processedMatches += safeNumber(meta.batch_count, 0);
    lastTotalLiveMatches = safeNumber(
      meta.total_live_matches,
      lastTotalLiveMatches
    );
    aggregate.batches_completed++;
    aggregate.predictions_created += safeNumber(meta.predictions_created, 0);
    aggregate.predictions_existing += safeNumber(meta.predictions_existing, 0);
    aggregate.predictions_failed += safeNumber(meta.predictions_failed, 0);
    aggregate.telegram_retry_processed += safeNumber(
      meta.telegram_retry_processed,
      0
    );
    aggregate.telegram_retry_sent += safeNumber(meta.telegram_retry_sent, 0);
    aggregate.telegram_retry_failed += safeNumber(
      meta.telegram_retry_failed,
      0
    );
    aggregate.instant_validated += safeNumber(meta.instant_validated, 0);
    aggregate.instant_validation_deferred += safeNumber(
      meta.instant_validation_deferred,
      0
    );
    aggregate.updated_running += safeNumber(meta.updated_running, 0);
    aggregate.bsd_rate_limited = aggregate.bsd_rate_limited || Boolean(meta.bsd_rate_limited);
    if (meta.bsd_skipped) aggregate.bsd_skipped_batches++;
    aggregate.bsd_stats_calls += safeNumber(meta.bsd_stats_calls, 0);
    aggregate.bsd_stats_enriched += safeNumber(meta.bsd_stats_enriched, 0);
    aggregate.api_football_stats_enriched += safeNumber(meta.api_football_stats_enriched, 0);
    aggregate.espn_summary_stats_pairs_gained += safeNumber(meta.espn_summary_stats_pairs_gained, 0);
    aggregate.matches_missing_minute += safeNumber(meta.matches_missing_minute, 0);
    for (const market of ["shots", "corners", "fouls"]) {
      const source = meta.market_diagnostics?.[market] || {};
      const target = aggregate.market_diagnostics[market];
      for (const [reason, count] of Object.entries(source)) {
        target[reason] = safeNumber(target[reason], 0) + safeNumber(count, 0);
      }
    }
    hasMore = Boolean(result?.has_more);
    const nextCursor = result?.next_cursor == null ? null : String(result.next_cursor);
    if (hasMore && (!nextCursor || nextCursor === cursor)) {
      throw new Error(
        `Refresh batch bloqu\xE9: cursor n'avance pas (${String(cursor)})`
      );
    }
    cursor = nextCursor;
    batchNumber++;
  }
  return {
    processed_matches: processedMatches,
    total_live_matches: lastTotalLiveMatches,
    has_more: hasMore,
    next_cursor: cursor,
    meta: {
      ...aggregate,
      requested_batch_size: batchSize,
      max_batches: LIVE_REFRESH_MAX_BATCHES,
      truncated: hasMore
    }
  };
}
async function getStoredMergedContextForPrediction(pred) {
  try {
    const { data, error } = await supabase.from(T_STATS_MERGED).select("primary_match_id, event_date, home_team, away_team, is_finished, minute, merged_stats, merged_match_json, updated_at").eq("primary_match_id", String(pred?.match_id ?? "")).order("updated_at", { ascending: false }).limit(1).maybeSingle();
    if (error) return null;
    return data || null;
  } catch {
    return null;
  }
}
function requiredMarketStatKey(predictionType) {
  if (predictionType === "total_corners") return "corner_kicks";
  if (predictionType === "total_shots") return "total_shots";
  if (predictionType === "total_fouls") return "fouls";
  return null;
}
function hasRequiredFinalStats(stats, predictionType) {
  const key = requiredMarketStatKey(predictionType);
  return key ? hasCompleteStatPair(stats, key) : false;
}
async function fetchEspnSummary(eventId) {
  try {
    return await fetchSharedEspnSummary(eventId, espnStore);
  } catch (error) {
    console.warn("ESPN summary unavailable:", eventId, error);
    return null;
  }
}
function mergeEspnSummaryStatsIntoEvent(event, summary) {
  if (!event || !summary) return event;
  const competition = event?.competitions?.[0];
  if (!competition) return event;
  const boxTeams = Array.isArray(summary?.boxscore?.teams) ? summary.boxscore.teams : [];
  if (!boxTeams.length) return event;
  const competitors = (competition?.competitors || []).map((competitor) => {
    const teamId = String(competitor?.team?.id || "");
    const box = boxTeams.find((x) => String(x?.team?.id || "") === teamId);
    if (!box) return competitor;
    return { ...competitor, statistics: box?.statistics || competitor?.statistics || [] };
  });
  return {
    ...event,
    competitions: [{ ...competition, competitors }]
  };
}
async function fetchEspnFinalForPrediction(pred, stored) {
  const reference = stored?.merged_match_json || {
    home_team: pred?.home_team,
    away_team: pred?.away_team,
    league_name: pred?.league_name,
    event_date: stored?.event_date || pred?.created_at
  };
  const dateKey = toDateKey(stored?.event_date || pred?.created_at);
  try {
    const scoreboard = await fetchEspnScoreboard(dateKey, false);
    const events = Array.isArray(scoreboard?.events) ? scoreboard.events : [];
    const knownEspnId = String(
      stored?.merged_match_json?.raw_data?.merge_meta?.espn_match_id || stored?.merged_match_json?.raw_data?.event_id || ""
    );
    let rawEvent = null;
    if (knownEspnId) rawEvent = events.find((e) => String(e?.id || "") === knownEspnId) || null;
    if (!rawEvent) {
      let bestScore = 0;
      for (const event of events) {
        const normalized2 = normalizeEspnEventToOriginalMatch(event);
        if (!normalized2) continue;
        const score = sameMatchScore(reference, normalized2);
        if (score > bestScore) {
          bestScore = score;
          rawEvent = event;
        }
      }
      if (bestScore < 0.65) rawEvent = null;
    }
    if (!rawEvent) return null;
    let normalized = normalizeEspnEventToOriginalMatch(rawEvent);
    if (!normalized?.is_finished) return null;
    if (!hasRequiredFinalStats(normalized?.live_stats, String(pred?.prediction_type || ""))) {
      const summary = await fetchEspnSummary(String(rawEvent?.id || ""));
      if (summary) {
        rawEvent = mergeEspnSummaryStatsIntoEvent(rawEvent, summary);
        normalized = normalizeEspnEventToOriginalMatch(rawEvent);
      }
    }
    if (!normalized?.is_finished) return null;
    if (!hasRequiredFinalStats(normalized?.live_stats, String(pred?.prediction_type || ""))) return null;
    return normalized;
  } catch (e) {
    console.warn("ESPN final lookup failed:", e);
    return null;
  }
}
async function resolveFinalEventAndStats(pred, storedOverride = void 0) {
  const predictionType = String(pred?.prediction_type || "");
  const isHistoricalValidated = pred?.validated === true;
  const stored = storedOverride === void 0 ? await getStoredMergedContextForPrediction(pred) : storedOverride;
  if (isHistoricalValidated) {
    const espn = await fetchEspnFinalForPrediction(pred, stored);
    if (espn) return { event: espn, stats: espn.live_stats, source: "espn_final" };
  }
  try {
    const bsdEvent = await fetchBSD(`/events/${pred.match_id}/`);
    if (isFinishedEvent(bsdEvent)) {
      let stats = bsdEvent?.live_stats || null;
      if (!hasRequiredFinalStats(stats, predictionType)) {
        try {
          const finalStatsPayload = await fetchBSD(`/events/${pred.match_id}/stats/`);
          stats = normalizeBsdStatsPayload(finalStatsPayload);
        } catch {
        }
      }
      if (hasRequiredFinalStats(stats, predictionType)) {
        return { event: bsdEvent, stats, source: "bsd_final" };
      }
    }
  } catch {
  }
  if (!isHistoricalValidated) {
    const espn = await fetchEspnFinalForPrediction(pred, stored);
    if (espn) return { event: espn, stats: espn.live_stats, source: "espn_final" };
  }
  if (stored?.is_finished === true && hasRequiredFinalStats(stored?.merged_stats, predictionType)) {
    const event = stored?.merged_match_json || {
      id: pred?.match_id,
      home_team: pred?.home_team,
      away_team: pred?.away_team,
      is_finished: true,
      live_stats: stored?.merged_stats
    };
    return { event, stats: stored.merged_stats, source: "stored_final" };
  }
  return null;
}
async function validatePredictionsNow() {
  const backlogCutoff = new Date(Date.now() - 4 * 3600 * 1e3).toISOString();
  const currentResult = await supabase.from("live_predictions").select("*").eq("validated", false).gte("created_at", backlogCutoff).order("created_at", { ascending: false }).limit(10);
  if (currentResult.error) throw currentResult.error;
  const historicalPendingResult = await supabase.from("live_predictions").select("*").eq("validated", false).eq("telegram_sent", true).lt("created_at", backlogCutoff).order("created_at", { ascending: false }).limit(10);
  if (historicalPendingResult.error) throw historicalPendingResult.error;
  let backlogResult = await supabase.from("live_predictions").select("*").eq("validated", true).is("final_value", null).eq("telegram_sent", true).lt("created_at", backlogCutoff).order("created_at", { ascending: false }).limit(10);
  if (backlogResult.error && isUndefinedColumnError(backlogResult.error)) {
    backlogResult = { data: [], error: null };
  }
  if (backlogResult.error) throw backlogResult.error;
  const seen = /* @__PURE__ */ new Set();
  const pending = [
    ...currentResult.data || [],
    ...historicalPendingResult.data || [],
    ...backlogResult.data || []
  ].filter((row) => {
    const id = String(row?.id ?? "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
  if (!pending.length) return { validated: 0, finalized_existing: 0, skipped: 0, failed: 0 };
  const storedByMatch = /* @__PURE__ */ new Map();
  let bulkContextLoaded = false;
  const matchIds = [...new Set(pending.map((p) => String(p?.match_id || "")).filter(Boolean))];
  if (matchIds.length) {
    const { data: contexts, error: bulkError } = await supabase.from(T_STATS_MERGED).select("primary_match_id, event_date, home_team, away_team, is_finished, minute, merged_stats, merged_match_json, updated_at").in("primary_match_id", matchIds).order("updated_at", { ascending: false }).limit(200);
    if (!bulkError) {
      bulkContextLoaded = true;
      for (const row of contexts || []) {
        const matchId = String(row?.primary_match_id || "");
        if (matchId && !storedByMatch.has(matchId)) storedByMatch.set(matchId, row);
      }
    } else {
      console.warn("Bulk final contexts unavailable; using per-match fallback", bulkError);
    }
  }
  pending.sort((a, b2) => {
    const left = storedByMatch.get(String(a?.match_id))?.event_date || a?.created_at;
    const right = storedByMatch.get(String(b2?.match_id))?.event_date || b2?.created_at;
    return toDateKey(left).localeCompare(toDateKey(right));
  });
  let validated = 0;
  let finalizedExisting = 0;
  let skipped = 0;
  let failed = 0;
  const skipReasons = {};
  const bumpSkip = (reason) => {
    skipped++;
    skipReasons[reason] = (skipReasons[reason] || 0) + 1;
  };
  for (const pred of pending) {
    if (pred.telegram_sent !== true) {
      bumpSkip("telegram_not_sent");
      continue;
    }
    const isHistoricalPending = pred.validated !== true && String(pred.created_at || "") < backlogCutoff;
    const stored = bulkContextLoaded ? storedByMatch.get(String(pred?.match_id)) || null : void 0;
    const resolvedFinal = await resolveFinalEventAndStats(pred, stored);
    if (!resolvedFinal) {
      bumpSkip("final_source_unavailable");
      continue;
    }
    const ev = resolvedFinal.event;
    const stats = resolvedFinal.stats;
    const threshold = safeNumber(pred.threshold, 0);
    let finalValue = 0;
    let ok = false;
    if (pred.prediction_type === "total_shots") {
      finalValue = safeNumber(stats?.home?.total_shots) + safeNumber(stats?.away?.total_shots);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_corners") {
      finalValue = safeNumber(stats?.home?.corner_kicks) + safeNumber(stats?.away?.corner_kicks);
      ok = finalValue > threshold;
    } else if (pred.prediction_type === "total_fouls") {
      finalValue = safeNumber(stats?.home?.fouls) + safeNumber(stats?.away?.fouls);
      ok = finalValue > threshold;
    } else {
      bumpSkip("unsupported_market");
      continue;
    }
    if (pred.validated === true) {
      try {
        await updatePredictionSafe(String(pred.id), {
          current_value: finalValue,
          final_value: finalValue,
          headroom: Number((finalValue - threshold).toFixed(2)),
          updated_at: (/* @__PURE__ */ new Date()).toISOString()
        });
        finalizedExisting++;
      } catch (e) {
        failed++;
        console.error("Final headroom enrichment failed:", e);
      }
      continue;
    }
    try {
      const validation = await validatePredictionWithMerge({
        predRow: pred,
        outcome: ok ? "success" : "failure",
        currentValue: finalValue,
        validation_type: "final"
      });
      if (!validation.transitioned) {
        bumpSkip("validation_transition_noop");
        continue;
      }
      const keptId = validation.id;
      if (isHistoricalPending) {
        validated++;
        continue;
      }
      await insertNotification({
        user_id: "all",
        type: "prediction_validated",
        title: "Pr\xE9diction valid\xE9e",
        message: `${pred.match_name}
Type: ${pred.prediction_type}
Pronostic (seuil): ${pred.threshold}
Valeur finale: ${finalValue}
R\xE9sultat: ${ok ? "\u2705 r\xE9ussi" : "\u274C \xE9chou\xE9"}`,
        priority: "normal",
        read: false,
        related_prediction_id: keptId
      });
      const telegramMatch = await getTelegramMatchFromCache(pred, ev);
      await sendTelegramValidationResult(
        telegramMatch,
        pred,
        ok ? "success" : "failure",
        finalValue,
        "final",
        keptId
      );
      validated++;
    } catch (e) {
      failed++;
      console.error("validatePredictionsNow failed (ignored):", e);
    }
  }
  return {
    validated,
    finalized_existing: finalizedExisting,
    skipped,
    failed,
    skip_reasons: skipReasons,
    current_candidates: currentResult.data?.length || 0,
    historical_pending_candidates: historicalPendingResult.data?.length || 0,
    backlog_candidates: backlogResult.data?.length || 0
  };
}
async function getRawMatchMap(matchIds) {
  const ids = [...new Set((matchIds || []).map(String).filter(Boolean))];
  const matchMap = /* @__PURE__ */ new Map();
  if (!ids.length) return matchMap;
  const { data: mrows, error: mErr } = await supabase.from("matches_live").select("id, raw_data").in("id", ids);
  if (mErr) {
    console.error("matches_live fetch failed:", mErr);
    return matchMap;
  }
  for (const r of mrows || []) matchMap.set(String(r.id), r.raw_data || {});
  return matchMap;
}
function enrichPredictionForUi(p, raw) {
  return {
    id: p.id,
    match_id: String(p.match_id),
    home_team: p.home_team ?? raw.home_team ?? null,
    away_team: p.away_team ?? raw.away_team ?? null,
    current_minute: p.minute ?? null,
    // minute du signal (fixe historique)
    league: raw.league ?? { name: p.league_name ?? null },
    league_id: raw.league_id ?? null,
    home_team_id: raw.home_team_id ?? null,
    away_team_id: raw.away_team_id ?? null,
    home_team_obj: raw.home_team_obj ?? null,
    away_team_obj: raw.away_team_obj ?? null,
    match: p.match_name,
    type: p.prediction_type,
    probability: Number(p.probability),
    message: p.message,
    pronostic: p.threshold,
    threshold: p.threshold,
    signal_value: p.signal_value ?? p.current_value ?? null,
    projected: p.projected_value ?? null,
    projected_value: p.projected_value ?? null,
    current: p.current_value,
    reliability: safeNumber(p.reliability_score, (Number(p.probability) || 0) * 100),
    model_fair_odds: p.model_fair_odds ?? null,
    bookmaker_odds: p.bookmaker_odds ?? null,
    implied_probability: p.implied_probability ?? null,
    edge: p.edge ?? null,
    expected_value: p.expected_value ?? null,
    value_score: p.value_score ?? null,
    data_quality_score: p.data_quality_score ?? null,
    freshness_seconds: p.freshness_seconds ?? null,
    source_count: p.source_count ?? null,
    source_confidence: p.source_confidence ?? null,
    signal_tier: p.signal_tier ?? null,
    pricing_mode: p.pricing_mode ?? null,
    line_candidate_count: p.line_candidate_count ?? null,
    line_candidate_rank: p.line_candidate_rank ?? null,
    baseline_threshold: p.baseline_threshold ?? null,
    historical_uplift_cap: p.historical_uplift_cap ?? null,
    selected_uplift: p.selected_uplift ?? null,
    model_version: p.model_version ?? null,
    final_value: p.final_value ?? null,
    headroom: p.headroom ?? null,
    validated: !!p.validated,
    outcome: p.outcome ?? null,
    validation_type: p.validation_type ?? null,
    validated_at: p.validated_at ?? null,
    timestamp: new Date(p.created_at).getTime(),
    created_at: p.created_at,
    signal_home_score: p.signal_home_score,
    signal_away_score: p.signal_away_score,
    signal_minute: p.signal_minute,
    signal_half1_home: p.signal_half1_home,
    signal_half1_away: p.signal_half1_away,
    signal_half2_home: p.signal_half2_home,
    signal_half2_away: p.signal_half2_away,
    home_score: p.signal_home_score ?? p.home_score ?? raw.home_score ?? 0,
    away_score: p.signal_away_score ?? p.away_score ?? raw.away_score ?? 0,
    minute: p.signal_minute ?? p.minute ?? null,
    live_odds: p.live_odds,
    stake_fcfa: p.stake_fcfa,
    potential_gain_fcfa: p.potential_gain_fcfa,
    odds_source: p.odds_source
  };
}
function dailyTodayUtc() {
  return (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
}
function dailyNormTeam(v) {
  return stripAccents(String(v ?? "")).toLowerCase().replace(/&/g, " and ").replace(/\b(fc|cf|sc|afc|club|football|soccer|the|de|da|do)\b/g, " ").replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}
function dailyTeamSimilarity(a, b2) {
  const aa = dailyNormTeam(a);
  const bb = dailyNormTeam(b2);
  if (!aa || !bb) return 0;
  if (aa === bb) return 1;
  if (aa.includes(bb) || bb.includes(aa)) return 0.92;
  const as = new Set(aa.split(" ").filter(Boolean));
  const bs = new Set(bb.split(" ").filter(Boolean));
  let intersection = 0;
  for (const x of as) if (bs.has(x)) intersection++;
  const union = (/* @__PURE__ */ new Set([...as, ...bs])).size || 1;
  return intersection / union;
}
function dailyEventHome(ev) {
  return ev?.home_team?.name ?? ev?.home_team ?? ev?.home?.name ?? ev?.teams?.home?.name ?? "";
}
function dailyEventAway(ev) {
  return ev?.away_team?.name ?? ev?.away_team ?? ev?.away?.name ?? ev?.teams?.away?.name ?? "";
}
function dailyEventLeague(ev) {
  return ev?.league?.name ?? ev?.competition?.name ?? ev?.league_name ?? "Football";
}
function dailyEventKickoff(ev) {
  return ev?.event_date ?? ev?.start_time ?? ev?.date ?? ev?.kickoff ?? null;
}
function dailyEventId(ev) {
  return ev?.id ?? ev?.event_id ?? null;
}
function dailyEventTeamId(ev, side) {
  const team = side === "home" ? ev?.home_team_obj ?? ev?.home ?? ev?.teams?.home ?? ev?.home_team : ev?.away_team_obj ?? ev?.away ?? ev?.teams?.away ?? ev?.away_team;
  return team?.id ?? team?.api_id ?? team?.team_id ?? ev?.[side + "_team_id"] ?? ev?.[side + "_id"] ?? null;
}
function dailyEventLogo(ev, side) {
  const team = side === "home" ? ev?.home_team_obj ?? ev?.home ?? ev?.teams?.home ?? ev?.home_team : ev?.away_team_obj ?? ev?.away ?? ev?.teams?.away ?? ev?.away_team;
  const direct = team?.logo_url ?? team?.logo ?? team?.image_url ?? team?.image ?? ev?.[side + "_logo"] ?? null;
  if (typeof direct === "string" && direct.trim()) return direct;
  const teamId = dailyEventTeamId(ev, side);
  if (teamId != null && /^\d+$/.test(String(teamId))) {
    return `${BSD_IMG_BASE}/team/${teamId}/?bg=transparent`;
  }
  return null;
}
function dailyResultRows(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.events)) return payload.events;
  return [];
}
function dailyFindEventForProno(prono, events) {
  const ph = prono?.home_team;
  const pa = prono?.away_team;
  let best = null;
  let bestScore = 0;
  for (const ev of events || []) {
    const direct = dailyTeamSimilarity(ph, dailyEventHome(ev)) * 0.5 + dailyTeamSimilarity(pa, dailyEventAway(ev)) * 0.5;
    const reverse = dailyTeamSimilarity(ph, dailyEventAway(ev)) * 0.5 + dailyTeamSimilarity(pa, dailyEventHome(ev)) * 0.5;
    const score = Math.max(direct, reverse);
    if (score > bestScore) {
      bestScore = score;
      best = ev;
    }
  }
  return bestScore >= 0.78 ? best : null;
}
function dailyCollectOddsObjects(value, out = [], depth = 0) {
  if (depth > 8 || value == null) return out;
  if (Array.isArray(value)) {
    for (const x of value) dailyCollectOddsObjects(x, out, depth + 1);
    return out;
  }
  if (typeof value !== "object") return out;
  const hasOdds = value.decimal_odds != null || value.odds_decimal != null || value.odds != null || value.price != null;
  const hasMarket = value.market != null || value.market_type != null || value.market_name != null;
  const hasOutcome = value.outcome != null || value.selection != null || value.name != null;
  if (hasOdds && hasMarket && hasOutcome) out.push(value);
  for (const x of Object.values(value)) {
    if (x && typeof x === "object") {
      dailyCollectOddsObjects(x, out, depth + 1);
    }
  }
  return out;
}
function dailyNormMarket(v) {
  return String(v ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}
function dailyNormOutcome(v) {
  return String(v ?? "").trim().toUpperCase().replace(/\s+/g, "");
}
function dailyOutcomeAliases(wanted) {
  const target = dailyNormOutcome(wanted);
  if (target === "1X") {
    return /* @__PURE__ */ new Set([
      "1X",
      "HOME_DRAW",
      "HOMEDRAW",
      "HOMEORDRAW",
      "HOME_OR_DRAW",
      "1_X",
      "HD"
    ]);
  }
  if (target === "X2") {
    return /* @__PURE__ */ new Set([
      "X2",
      "DRAW_AWAY",
      "DRAWAWAY",
      "DRAWORAWAY",
      "DRAW_OR_AWAY",
      "X_2",
      "DA"
    ]);
  }
  return /* @__PURE__ */ new Set([
    "12",
    "HOME_AWAY",
    "HOMEAWAY",
    "HOMEORAWAY",
    "HOME_OR_AWAY",
    "1_2",
    "HA"
  ]);
}
function dailyOutcomeKey(v) {
  return String(v ?? "").trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}
function dailyExtractPrice(v) {
  if (typeof v === "number" || typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) && n > 1.01 ? Number(n.toFixed(2)) : null;
  }
  if (!v || typeof v !== "object") return null;
  for (const key of [
    "price",
    "odds",
    "decimal_odds",
    "odds_decimal",
    "value",
    "consensus_price"
  ]) {
    const n = Number(v?.[key]);
    if (Number.isFinite(n) && n > 1.01) return Number(n.toFixed(2));
  }
  return null;
}
function dailyExtractTargetFromMap(value, aliases) {
  if (!value || typeof value !== "object") return null;
  for (const [key, raw] of Object.entries(value)) {
    if (aliases.has(dailyOutcomeKey(key))) {
      const price = dailyExtractPrice(raw);
      if (price != null) return price;
    }
  }
  return null;
}
function dailyPickDoubleChanceOdds(payload, wanted) {
  const aliases = dailyOutcomeAliases(wanted);
  const directContainers = [
    payload?.odds?.double_chance,
    payload?.double_chance,
    payload?.consensus?.double_chance,
    payload?.odds_consensus?.double_chance,
    payload?.markets?.double_chance
  ];
  for (const container of directContainers) {
    const price = dailyExtractTargetFromMap(container, aliases);
    if (price != null) {
      return { odds: price, source: "consensus" };
    }
  }
  const marketCandidates = [];
  function walk(value, depth = 0) {
    if (depth > 8 || value == null) return;
    if (Array.isArray(value)) {
      for (const x of value) walk(x, depth + 1);
      return;
    }
    if (typeof value !== "object") return;
    const marketName = dailyNormMarket(
      value?.market ?? value?.market_type ?? value?.market_name ?? value?.market_kind ?? value?.market_family ?? value?.kind ?? value?.family
    );
    const looksDc = marketName.includes("double_chance") || marketName === "dc" || marketName.startsWith("dc_") || marketName.includes("doublechance");
    if (looksDc) marketCandidates.push(value);
    for (const x of Object.values(value)) {
      if (x && typeof x === "object") walk(x, depth + 1);
    }
  }
  walk(payload);
  const prices = [];
  for (const market of marketCandidates) {
    for (const container of [
      market?.prices,
      market?.consensus,
      market?.consensus_prices,
      market?.odds,
      market?.selections
    ]) {
      const direct = dailyExtractTargetFromMap(container, aliases);
      if (direct != null) prices.push(direct);
    }
    const outcome = dailyOutcomeKey(
      market?.outcome ?? market?.selection ?? market?.name
    );
    if (aliases.has(outcome)) {
      const p = dailyExtractPrice(market);
      if (p != null) prices.push(p);
    }
    for (const book of market?.bookmakers || []) {
      const p = dailyExtractTargetFromMap(
        book?.prices ?? book?.odds ?? book,
        aliases
      );
      if (p != null) prices.push(p);
    }
  }
  for (const row of dailyCollectOddsObjects(payload)) {
    const market = dailyNormMarket(
      row?.market ?? row?.market_type ?? row?.market_name
    );
    const outcome = dailyOutcomeKey(
      row?.outcome ?? row?.selection ?? row?.name
    );
    if ((market.includes("double_chance") || market.startsWith("dc_")) && aliases.has(outcome)) {
      const p = dailyExtractPrice(row);
      if (p != null) prices.push(p);
    }
  }
  if (!prices.length) return null;
  const avg = prices.reduce((a, b2) => a + b2, 0) / prices.length;
  return {
    odds: Number(avg.toFixed(2)),
    source: prices.length > 1 ? "consensus_avg" : "consensus"
  };
}
function dailyTableMissing(error) {
  const code = String(error?.code || "");
  const message = String(error?.message || "").toLowerCase();
  return code === "42P01" || code === "PGRST205" || message.includes("daily_predictions") && (message.includes("could not find") || message.includes("does not exist") || message.includes("schema cache"));
}
function dailySourceOdds(p) {
  const candidates = [
    p?.odds_snapshot,
    p?.consensus_odds,
    p?.bookmaker_odds,
    p?.odds,
    p?.odd,
    p?.cote
  ];
  for (const value of candidates) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 1.01) {
      return Number(n.toFixed(2));
    }
  }
  return null;
}
function dailyIsLikelyFootball(p) {
  const text2 = [
    p?.competition,
    p?.league_name,
    p?.league,
    p?.home_team,
    p?.away_team
  ].filter(Boolean).join(" ").toLowerCase();
  return !/\b(npb|mlb|kbo|cpbl|baseball|basketball|basket|nba|wnba|nhl|ice hockey|hockey|cricket|volleyball|handball|nfl|american football)\b/i.test(text2);
}
var dailySiteDataCache = null;
var DAILY_SITE_DATA_TTL_MS = 10 * 60 * 1e3;
async function dailyLoadSiteDataMap() {
  const now = Date.now();
  if (dailySiteDataCache && now - dailySiteDataCache.at < DAILY_SITE_DATA_TTL_MS) {
    return dailySiteDataCache.byId;
  }
  const byId = /* @__PURE__ */ new Map();
  try {
    const base = SITE_URL.replace(/\/$/, "");
    const res = await fetch(`${base}/data.json`, {
      headers: { "Accept": "application/json" }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();
    for (const row of payload?.matches || []) {
      if (row?.id != null) byId.set(String(row.id), row);
    }
    dailySiteDataCache = { at: now, byId };
  } catch (e) {
    console.warn("data.json public indisponible pour les logos daily:", e?.message || String(e));
    dailySiteDataCache = { at: now, byId };
  }
  return byId;
}
function dailyAbsoluteSiteAsset(path) {
  const raw = String(path || "").trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return raw;
  const base = SITE_URL.replace(/\/$/, "");
  return `${base}/${raw.replace(/^\/+/, "")}`;
}
async function dailyEnrichSourceRows(sourceRows) {
  const byId = await dailyLoadSiteDataMap();
  return (sourceRows || []).map((p) => {
    const raw = byId.get(String(p?.match_id ?? p?.id ?? ""));
    if (!raw) return p;
    return {
      ...p,
      home_logo: p?.home_logo ?? dailyAbsoluteSiteAsset(raw?.home_logo),
      away_logo: p?.away_logo ?? dailyAbsoluteSiteAsset(raw?.away_logo),
      event_date: p?.event_date ?? raw?.event_date ?? null,
      competition: p?.competition ?? raw?.league ?? null
    };
  });
}
async function dailyGetSourcePronos(date2) {
  const { data, error } = await supabase.from("pronostics").select("*").eq("date", date2).order("xpronos_score", { ascending: false });
  if (error) throw error;
  return (data || []).filter((p) => {
    const pick = String(p?.prediction || "").toUpperCase();
    return ["1X", "X2", "12"].includes(pick) && dailyIsLikelyFootball(p);
  });
}
function dailyFallbackRows(date2, sourceRows) {
  return (sourceRows || []).map((p) => {
    const outcome = String(p?.prediction || "").toUpperCase();
    const odds = dailySourceOdds(p);
    const stake = DAILY_DEFAULT_STAKE;
    return {
      id: `source-${String(p?.match_id ?? p?.id ?? crypto.randomUUID())}`,
      prediction_date: date2,
      source_match_id: String(p?.match_id ?? p?.id ?? ""),
      bsd_event_id: null,
      home_team: p?.home_team ?? "\xC9quipe domicile",
      away_team: p?.away_team ?? "\xC9quipe ext\xE9rieure",
      league_name: p?.competition ?? p?.league_name ?? p?.league ?? "Football",
      kickoff: p?.event_date ?? p?.kickoff ?? p?.start_time ?? date2,
      home_logo: p?.home_logo ?? null,
      away_logo: p?.away_logo ?? null,
      market_type: "double_chance",
      market_label: `Double chance ${outcome}`,
      outcome,
      line: null,
      odds_snapshot: odds,
      odds_source: odds ? "source" : null,
      odds_captured_at: p?.updated_at ?? p?.created_at ?? null,
      stake,
      potential_gain: odds ? Math.round(stake * odds) : null,
      confidence: safeNumber(p?.confidence, 0),
      xpronos_score: safeNumber(p?.xpronos_score, 0),
      source_category: p?.category ?? null,
      source_badge: p?.badge ?? null,
      status: "accepted",
      validated: false,
      fallback_source: true
    };
  });
}
async function dailyGetForUi(date2) {
  const stored = await supabase.from("daily_predictions").select("*").eq("prediction_date", date2).order("kickoff", { ascending: true });
  if (!stored.error && stored.data?.length) {
    return {
      date: date2,
      predictions: stored.data,
      count: stored.data.length,
      source: "daily_predictions",
      snapshot_available: true
    };
  }
  if (stored.error && !dailyTableMissing(stored.error)) {
    console.warn("daily_predictions read failed; fallback pronostics:", stored.error);
  }
  let sourceRows = [];
  try {
    sourceRows = await dailyGetSourcePronos(date2);
    sourceRows = await dailyEnrichSourceRows(sourceRows);
  } catch (e) {
    console.error("Fallback pronostics du jour indisponible:", e);
  }
  const fallback = dailyFallbackRows(date2, sourceRows);
  return {
    date: date2,
    predictions: fallback,
    count: fallback.length,
    source: "pronostics_fallback",
    snapshot_available: false,
    daily_predictions_table_missing: Boolean(stored.error && dailyTableMissing(stored.error))
  };
}
async function dailyFetchAllEventsForDate(date2) {
  const all = [];
  const pageSize = 200;
  for (let offset = 0; offset < 1200; offset += pageSize) {
    const payload = await fetchBSD("/events/", {
      date_from: date2,
      date_to: date2,
      limit: String(pageSize),
      offset: String(offset)
    });
    const rows = dailyResultRows(payload);
    all.push(...rows);
    const total = safeNumber(payload?.count, all.length);
    if (rows.length < pageSize || all.length >= total) break;
  }
  return all;
}
async function dailyFetchBsdConsensusDoubleChance(eventIdValue, outcome) {
  const target = String(outcome || "").toUpperCase();
  if (!["1X", "12", "X2"].includes(target)) return null;
  const payload = await fetchBSD("/odds/", {
    event_id: String(eventIdValue),
    market: "double_chance",
    outcome: target,
    limit: "20"
  });
  const rows = dailyResultRows(payload);
  const candidates = rows.map((row) => ({
    odds: safeNumber(
      row?.decimal_odds ?? row?.odds_decimal ?? row?.price ?? row?.odds,
      0
    ),
    bookmaker_slug: String(row?.bookmaker_slug || ""),
    bookmaker_name: String(row?.bookmaker_name || ""),
    bookmaker_count: row?.bookmaker_count ?? null
  })).filter((row) => row.odds > 1.01);
  if (!candidates.length) return null;
  const consensus = candidates.find(
    (row) => row.bookmaker_slug.toLowerCase() === "consensus" || row.bookmaker_name.toLowerCase() === "consensus"
  ) || candidates[0];
  return {
    odds: Number(consensus.odds.toFixed(2)),
    source: "bsd_consensus",
    bookmaker_count: consensus.bookmaker_count
  };
}
async function dailyGenerateSnapshots() {
  const date2 = dailyTodayUtc();
  const pronos = await dailyEnrichSourceRows(
    await dailyGetSourcePronos(date2)
  );
  if (!pronos.length) {
    return {
      date: date2,
      source_count: 0,
      inserted: 0,
      skipped: 0,
      message: "Aucun prono source pour aujourd'hui"
    };
  }
  const tableProbe = await supabase.from("daily_predictions").select("id").limit(1);
  if (tableProbe.error) {
    if (dailyTableMissing(tableProbe.error)) {
      return {
        date: date2,
        source_count: pronos.length,
        inserted: 0,
        skipped: pronos.length,
        fallback_available: true,
        table_missing: true,
        message: "daily_predictions absente: le site utilise temporairement pronostics comme fallback"
      };
    }
    throw tableProbe.error;
  }
  let events = [];
  try {
    events = await dailyFetchAllEventsForDate(date2);
  } catch (e) {
    const quotaExhausted = isBSDQuotaError(e);
    const nextMidnight = /* @__PURE__ */ new Date();
    nextMidnight.setUTCDate(nextMidnight.getUTCDate() + 1);
    nextMidnight.setUTCHours(0, 0, 0, 0);
    return {
      date: date2,
      source_count: pronos.length,
      inserted: 0,
      skipped: pronos.length,
      fallback_available: true,
      quota_exhausted: quotaExhausted,
      retry_after_utc: quotaExhausted ? nextMidnight.toISOString() : null,
      events_error: e?.message || String(e)
    };
  }
  let inserted = 0;
  let skipped = 0;
  const details = [];
  for (const p of pronos) {
    const outcome = String(p?.prediction || "").toUpperCase();
    const existing = await supabase.from("daily_predictions").select("id").eq("prediction_date", date2).eq("source_match_id", String(p?.match_id)).eq("market_type", "double_chance").eq("outcome", outcome).limit(1).maybeSingle();
    if (existing.error) throw existing.error;
    if (existing.data?.id) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "already_snapshotted"
      });
      continue;
    }
    const ev = dailyFindEventForProno(p, events);
    if (!ev) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "bsd_event_not_found"
      });
      continue;
    }
    let picked = null;
    let oddsError = null;
    const bsdEventId = dailyEventId(ev);
    try {
      picked = await dailyFetchBsdConsensusDoubleChance(
        bsdEventId,
        outcome
      );
    } catch (e) {
      oddsError = e?.message || String(e);
      if (isBSDQuotaError(e)) {
        details.push({
          match_id: p?.match_id,
          status: "odds_quota_exhausted",
          bsd_event_id: bsdEventId,
          error: oddsError
        });
        break;
      }
    }
    if (!picked) {
      picked = dailyPickDoubleChanceOdds(ev, outcome);
    }
    if (!picked && !oddsError) {
      try {
        const oddsPayload = await fetchBSD(
          `/events/${bsdEventId}/odds/`
        );
        picked = dailyPickDoubleChanceOdds(oddsPayload, outcome);
      } catch (e) {
        oddsError = e?.message || String(e);
      }
    }
    if (!picked) {
      skipped++;
      details.push({
        match_id: p?.match_id,
        status: "consensus_odds_not_found",
        bsd_event_id: bsdEventId,
        error: oddsError
      });
      continue;
    }
    const stake = DAILY_DEFAULT_STAKE;
    const odds = Number(picked.odds.toFixed(2));
    const gain = Math.round(stake * odds);
    const rawBsdId = dailyEventId(ev);
    const numericBsdId = Number(rawBsdId);
    const row = {
      prediction_date: date2,
      source_match_id: String(p?.match_id),
      bsd_event_id: Number.isFinite(numericBsdId) ? numericBsdId : null,
      home_team: p?.home_team || dailyEventHome(ev),
      away_team: p?.away_team || dailyEventAway(ev),
      league_name: p?.competition || p?.league_name || dailyEventLeague(ev),
      kickoff: dailyEventKickoff(ev) || p?.event_date || null,
      home_logo: p?.home_logo || dailyEventLogo(ev, "home"),
      away_logo: p?.away_logo || dailyEventLogo(ev, "away"),
      market_type: "double_chance",
      market_label: `Double chance ${outcome}`,
      outcome,
      line: null,
      odds_snapshot: odds,
      odds_source: picked.source || "consensus",
      odds_captured_at: nowIso(),
      stake,
      potential_gain: gain,
      confidence: safeNumber(p?.confidence, 0),
      xpronos_score: safeNumber(p?.xpronos_score, 0),
      source_category: p?.category || null,
      source_badge: p?.badge || null,
      status: "accepted",
      validated: false
    };
    const { error } = await supabase.from("daily_predictions").insert(row);
    if (error) {
      if (String(error?.code || "") === "23505") {
        skipped++;
        details.push({
          match_id: p?.match_id,
          status: "duplicate"
        });
        continue;
      }
      throw error;
    }
    inserted++;
    details.push({
      match_id: p?.match_id,
      status: "inserted",
      odds,
      outcome
    });
  }
  return {
    date: date2,
    source_count: pronos.length,
    bsd_events_count: events.length,
    matched_events: details.filter(
      (d) => String(d?.status) !== "bsd_event_not_found"
    ).length,
    unmatched_events: details.filter(
      (d) => String(d?.status) === "bsd_event_not_found"
    ).length,
    inserted,
    skipped,
    details
  };
}
async function dailyValidateSnapshots() {
  const today = dailyTodayUtc();
  const eligibleBefore = new Date(
    Date.now() - 105 * 60 * 1e3
  ).toISOString();
  const pending = await supabase.from("daily_predictions").select("*").eq("validated", false).lte("kickoff", eligibleBefore).lte("prediction_date", today).order("kickoff", { ascending: true });
  if (pending.error) {
    if (dailyTableMissing(pending.error)) {
      return {
        checked: 0,
        validated: 0,
        won: 0,
        lost: 0,
        table_missing: true
      };
    }
    throw pending.error;
  }
  if (!pending.data?.length) {
    return { checked: 0, validated: 0, won: 0, lost: 0 };
  }
  const byDate = /* @__PURE__ */ new Map();
  for (const p of pending.data) {
    const date2 = String(p?.prediction_date);
    if (!byDate.has(date2)) byDate.set(date2, []);
    byDate.get(date2).push(p);
  }
  let checked = 0;
  let validated = 0;
  let won = 0;
  let lost = 0;
  for (const [date2, preds] of byDate.entries()) {
    let events = [];
    try {
      const payload = await fetchBSD("/events/", {
        status: "finished",
        date_from: date2,
        date_to: date2,
        limit: "200"
      });
      events = dailyResultRows(payload).filter(isFinishedEvent);
    } catch (e) {
      console.warn("Validation daily: \xE9v\xE9nements termin\xE9s indisponibles", e);
      continue;
    }
    for (const p of preds) {
      checked++;
      let ev = events.find(
        (x) => String(dailyEventId(x)) === String(p?.bsd_event_id)
      );
      if (!ev) ev = dailyFindEventForProno(p, events);
      if (!ev || !isFinishedEvent(ev)) continue;
      const hs = safeNumber(
        ev?.home_score ?? ev?.home?.score ?? ev?.scores?.home,
        0
      );
      const as = safeNumber(
        ev?.away_score ?? ev?.away?.score ?? ev?.scores?.away,
        0
      );
      const outcome = String(p?.outcome || "").toUpperCase();
      let ok = false;
      if (p?.market_type !== "double_chance") continue;
      if (outcome === "1X") ok = hs >= as;
      else if (outcome === "X2") ok = as >= hs;
      else if (outcome === "12") ok = hs !== as;
      else continue;
      const status2 = ok ? "won" : "lost";
      const { error } = await supabase.from("daily_predictions").update({
        status: status2,
        final_home_score: hs,
        final_away_score: as,
        validated: true,
        validated_at: nowIso()
      }).eq("id", p.id).eq("validated", false);
      if (error) throw error;
      validated++;
      if (ok) won++;
      else lost++;
    }
  }
  return { checked, validated, won, lost };
}
serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  const url2 = new URL(req.url);
  const path = extractPath(url2, "live");
  try {
    const imgMatch = path.match(/^\/img\/(team|league|player)\/(\d+)\/?$/);
    if (imgMatch && req.method === "GET") {
      const type = imgMatch[1];
      const apiId = imgMatch[2];
      const upstream = await fetch(`${BSD_IMG_BASE}/${type}/${apiId}/`, {
        headers: { Authorization: `Token ${BSD_API_TOKEN}` }
      });
      if (!upstream.ok) {
        const t = await upstream.text().catch(() => "");
        return new Response(t || "Image not found", {
          status: upstream.status,
          headers: { ...corsHeaders, "Content-Type": upstream.headers.get("content-type") || "text/plain" }
        });
      }
      return new Response(upstream.body, {
        status: 200,
        headers: {
          ...corsHeaders,
          "Content-Type": upstream.headers.get("content-type") || "image/png",
          "Cache-Control": "public, max-age=31536000"
        }
      });
    }
    if (path === "/debug/events-finished" && req.method === "GET") {
      requireDebugAuth(url2);
      const date2 = url2.searchParams.get("date") || "2026-03-29";
      const tz = url2.searchParams.get("tz") || DEFAULT_TZ;
      const raw = url2.searchParams.get("raw") === "1";
      const data = await fetchBSD("/events/", {
        status: "finished",
        date_from: date2,
        date_to: date2,
        tz
      });
      if (raw) return json2(data);
      const compact = (data?.results || []).map((m) => ({
        id: m.id,
        event_date: m.event_date,
        status: m.status,
        period: m.period ?? null,
        home_team: m.home_team,
        away_team: m.away_team,
        score: `${m.home_score ?? "-"}-${m.away_score ?? "-"}`,
        has_live_stats: !!m.live_stats
      }));
      return json2({
        query: { status: "finished", date_from: date2, date_to: date2, tz },
        count: data?.count ?? compact.length,
        results: compact
      });
    }
    if (path === "/stats/sources" && req.method === "GET") {
      requireDebugAuth(url2);
      const limit = Math.min(safeNumber(url2.searchParams.get("limit"), 100), 500);
      const { data, error } = await supabase.from(T_STATS_SOURCES).select("*").order("updated_at", { ascending: false }).limit(limit);
      if (error) throw error;
      return json2({ sources: data || [] });
    }
    if (path === "/stats/merged" && req.method === "GET") {
      requireDebugAuth(url2);
      const limit = Math.min(safeNumber(url2.searchParams.get("limit"), 100), 500);
      const { data, error } = await supabase.from(T_STATS_MERGED).select("*").order("updated_at", { ascending: false }).limit(limit);
      if (error) throw error;
      return json2({ merged: data || [] });
    }
    if (path === "/refresh/batch" && req.method === "POST") {
      requireCronAuth(req, url2);
      const requestedBatchSize = Math.floor(
        safeNumber(
          url2.searchParams.get("batch_size"),
          LIVE_REFRESH_BATCH_SIZE
        )
      );
      const batchSize = Math.max(1, Math.min(5, requestedBatchSize));
      const cursor = url2.searchParams.get("cursor") || null;
      const allowTelegram = String(url2.searchParams.get("allow_telegram") || "1") !== "0";
      const skipBsd = String(url2.searchParams.get("skip_bsd") || "0") === "1";
      const useSnapshot = String(url2.searchParams.get("use_snapshot") || "0") === "1";
      const result = await refreshLiveDataBatch({
        cursor,
        batchSize,
        allowTelegram,
        skipBsd,
        useSnapshot
      });
      return json2({
        success: true,
        ...result
      });
    }
    if (path === "/telegram/status" && req.method === "GET") {
      requireCronAuth(req, url2);
      const predictionId = String(
        url2.searchParams.get("prediction_id") || ""
      ).trim();
      let q = supabase.from("live_predictions").select(
        "id, match_name, prediction_type, threshold, created_at, telegram_sent, telegram_attempts, telegram_last_attempt_at, telegram_last_error, telegram_pending_chat_ids, telegram_sent_at"
      ).order("created_at", { ascending: false }).limit(predictionId ? 1 : 20);
      if (predictionId) q = q.eq("id", predictionId);
      const { data, error } = await q;
      if (error) throw error;
      return json2({
        telegram_configured: Boolean(TELEGRAM_BOT_TOKEN) && telegramChatIds().length > 0,
        target_chat_count: telegramChatIds().length,
        predictions: data || []
      });
    }
    if (path === "/telegram/process-one" && req.method === "POST") {
      requireCronAuth(req, url2);
      const body = await req.json().catch(() => ({}));
      const predictionId = url2.searchParams.get("prediction_id") || String(body?.prediction_id || "").trim() || null;
      const result = predictionId ? await processTelegramPredictionById(predictionId) : await retryPendingTelegramLiveCoupons([], 1);
      return json2({
        success: safeNumber(result?.telegram_retry_failed, 0) === 0,
        isolated: true,
        background: false,
        prediction_id: predictionId,
        ...result
      });
    }
    if (path === "/refresh" && req.method === "POST") {
      requireCronAuth(req, url2);
      const refreshTask = (async () => {
        const lockOwner = crypto.randomUUID();
        let acquired = false;
        let releaseCursor = null;
        try {
          const { data, error } = await supabase.rpc(
            "claim_live_refresh",
            { p_owner: lockOwner }
          );
          if (error) throw error;
          if (!data) {
            console.log("LIVE_REFRESH_ALREADY_RUNNING", { at: nowIso() });
            return;
          }
          acquired = true;
          const { data: previousProgress, error: progressError } = await supabase.from("live_refresh_control").select("cursor").eq("key", "live_refresh").maybeSingle();
          if (progressError) throw progressError;
          releaseCursor = previousProgress?.cursor || null;
          const result = await refreshLiveDataInBatches(
            LIVE_REFRESH_BATCH_SIZE,
            lockOwner
          );
          releaseCursor = result.has_more ? result.next_cursor : null;
          await setCronRun("live_refresh", !result.has_more, {
            processed_matches: result.processed_matches,
            total_live_matches: result.total_live_matches,
            next_cursor: result.next_cursor,
            ...result.meta
          });
        } catch (e) {
          console.error("LIVE_REFRESH_BACKGROUND_ERROR", e);
          await setCronRun("live_refresh", false, {
            error: e?.message || String(e)
          });
        } finally {
          if (acquired) {
            try {
              const { error: releaseError } = await supabase.rpc(
                "release_live_refresh",
                { p_owner: lockOwner, p_cursor: releaseCursor }
              );
              if (releaseError) console.error("LIVE_REFRESH_RELEASE_FAILED", releaseError);
            } catch (e) {
              console.error("LIVE_REFRESH_RELEASE_FAILED", e?.message || String(e));
            }
          }
        }
        if (acquired) {
          try {
            await syncUpcomingFixtures();
          } catch (e) {
            console.warn("UPCOMING_PULSE_FAILED", e?.message || String(e));
          }
        }
      })();
      const edgeRuntime = globalThis.EdgeRuntime;
      if (edgeRuntime?.waitUntil) {
        edgeRuntime.waitUntil(refreshTask);
        return json2({
          accepted: true,
          background: true,
          message: "Refresh LIVE pris en charge; \xE9tat r\xE9el suivi dans cron_runs"
        }, 202);
      }
      await refreshTask;
      return json2({
        accepted: true,
        background: false,
        message: "Refresh LIVE ex\xE9cut\xE9; consulter cron_runs pour le r\xE9sultat"
      }, 202);
    }
    if (path === "/validate" && req.method === "POST") {
      requireCronAuth(req, url2);
      try {
        const result = await validatePredictionsNow();
        await setCronRun("live_validate", true, result);
        return json2({ success: true, ...result });
      } catch (e) {
        await setCronRun("live_validate", false, { error: e?.message || String(e) });
        throw e;
      }
    }
    if (path === "/matches" && req.method === "GET") {
      const matches = await getLiveMatchesFromDb();
      return json2({ matches });
    }
    if (path === "/opportunities" && req.method === "GET") {
      const opportunities = await getLiveOpportunitiesFromDb();
      return json2({ opportunities });
    }
    if (path === "/backtest/headroom" && req.method === "GET") {
      requireDebugAuth(url2);
      const days = safeNumber(url2.searchParams.get("days"), 90);
      const backtest = await getLiveHeadroomBacktest(days);
      return json2({ backtest });
    }
    if (path === "/today" && req.method === "GET") {
      const date2 = url2.searchParams.get("date") || (/* @__PURE__ */ new Date()).toISOString().slice(0, 10);
      const liveMatches = await getLiveMatchesFromDb().catch(() => []);
      let events = [];
      try {
        const cached = await espnStore.read("scoreboard:" + toDateKey(date2));
        const scoreboard = cached?.payload;
        events = (scoreboard?.events || []).map(normalizeEspnEventToOriginalMatch).filter(Boolean);
      } catch (e) {
        console.warn("ESPN /today unavailable:", e);
      }
      const { data: extraScheduled, error: scheduledError } = await supabase.from("live_scheduled_fixtures").select("fixture,updated_at,event_date").gte("event_date", new Date(Date.now() - 10 * 6e4).toISOString()).lte("event_date", new Date(Date.now() + 48 * 36e5).toISOString()).gte("updated_at", new Date(Date.now() - 6 * 36e5).toISOString()).order("event_date", { ascending: true }).limit(500);
      if (scheduledError) console.warn("Scheduled cache unavailable", scheduledError.message);
      const scheduled = events.filter((m) => !m.is_live && !m.is_finished);
      for (const row of extraScheduled || []) {
        const m = row.fixture;
        if (!m || m.is_live || m.is_finished) continue;
        const matchTime = Date.parse(String(getMatchEventDate(m) || ""));
        if (!Number.isFinite(matchTime) || matchTime < Date.now() - 10 * 6e4) continue;
        if (!scheduled.some((existing) => sameMatchScore(existing, m) >= 0.85)) scheduled.push(m);
      }
      scheduled.sort((a, b2) => Date.parse(getMatchEventDate(a)) - Date.parse(getMatchEventDate(b2)));
      const finished = events.filter((m) => m.is_finished);
      return json2({
        data: {
          live: { count: liveMatches.length, matches: liveMatches },
          scheduled: { count: scheduled.length, matches: scheduled },
          finished: { count: finished.length, matches: finished.slice(0, 10) }
        },
        meta: { source: "supabase+multisource-schedule", bsd_calls: 0, upstream_espn_calls: 0 }
      });
    }
    if (path === "/daily/today" && req.method === "GET") {
      const date2 = url2.searchParams.get("date") || dailyTodayUtc();
      const result = await dailyGetForUi(date2);
      return json2(result);
    }
    if (path === "/daily/generate" && req.method === "POST") {
      requireCronAuth(req, url2);
      const result = await dailyGenerateSnapshots();
      if (result?.quota_exhausted) {
        return json2({
          success: false,
          error: "BSD_DAILY_QUOTA_EXHAUSTED",
          ...result
        }, 429);
      }
      return json2({ success: true, ...result });
    }
    if (path === "/daily/validate" && req.method === "POST") {
      requireCronAuth(req, url2);
      const result = await dailyValidateSnapshots();
      return json2({ success: true, ...result });
    }
    if (path === "/predictions/history" && req.method === "GET") {
      const since = new Date(Date.now() - 48 * 3600 * 1e3).toISOString();
      const { data, error } = await supabase.from("live_predictions").select("*").gte("created_at", since).order("created_at", { ascending: false });
      if (error) throw error;
      const preds = data || [];
      const rawMap = await getRawMatchMap(preds.map((p) => String(p.match_id)));
      return json2({
        history: preds.map(
          (p) => enrichPredictionForUi(p, rawMap.get(String(p.match_id)) || {})
        )
      });
    }
    if (path === "/predictions/by-id" && req.method === "GET") {
      const id = url2.searchParams.get("id") || "";
      if (!id) return json2({ error: "id required" }, 400);
      const { data: p, error } = await supabase.from("live_predictions").select("*").eq("id", id).maybeSingle();
      if (error) throw error;
      if (!p) return json2({ error: "not found" }, 404);
      const { data: mrow, error: mErr } = await supabase.from("matches_live").select("raw_data").eq("id", String(p.match_id)).maybeSingle();
      if (mErr) console.error("matches_live by-id failed:", mErr);
      return json2({ prediction: enrichPredictionForUi(p, mrow?.raw_data || {}) });
    }
    if (path === "/notifications" && req.method === "GET") {
      const userId = url2.searchParams.get("user_id") || "all";
      const ids = userId === "all" ? ["all"] : ["all", userId];
      const { data, error } = await supabase.from("notifications").select("*").in("user_id", ids).order("created_at", { ascending: false }).limit(50);
      if (error) throw error;
      return json2({
        notifications: (data || []).map((n) => ({
          ...n,
          timestamp: new Date(n.created_at).getTime()
        }))
      });
    }
    if (path === "/notifications/mark-read" && req.method === "POST") {
      const body = await req.json().catch(() => ({}));
      const ids = Array.isArray(body.notification_ids) ? body.notification_ids : [];
      if (!ids.length) return json2({ success: true, updated: 0 });
      const { error } = await supabase.from("notifications").update({ read: true }).in("id", ids);
      if (error) throw error;
      return json2({ success: true, updated: ids.length });
    }
    return json2({ error: "Not found" }, 404);
  } catch (e) {
    console.error("live.ts error:", e);
    return json2({ error: e?.message || "Erreur serveur" }, 500);
  }
});
var index_neon_default = { fetch(req) {
  return neonGetHandler()(req);
} };
export {
  index_neon_default as default
};
/*! Bundled license information:

opentype.js/dist/opentype.js:
  (*! https://mths.be/codepointat v0.2.0 by @mathias *)
*/
