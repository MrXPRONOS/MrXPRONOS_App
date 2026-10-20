#!/usr/bin/env node
/* Compile LIVE JSX once at build-time; never ship Babel Standalone to clients. */
"use strict";
const fs=require("node:fs");
const path=require("node:path");
const crypto=require("node:crypto");
const esbuild=require("esbuild");
const root=path.resolve(__dirname,"..");
const htmlPath=path.join(root,"live.html");
const target=path.join(root,"assets/js/live.precompiled.js");
let html=fs.readFileSync(htmlPath,"utf8");
const match=html.match(/<script\s+type=["']text\/babel["']\s*>([\s\S]*?)<\/script>/i);
if (!match) {
  if (!html.includes("assets/js/live.precompiled.js")) throw new Error("LIVE: neither original JSX nor precompiled bundle referenced");
  if (!fs.existsSync(target)) throw new Error("LIVE: precompiled bundle referenced but missing");
  console.log("LIVE_PRECOMPILE_ALREADY_APPLIED", fs.statSync(target).size);
  process.exit(0);
}
const source=match[1];
if (source.length<25000 || !source.includes("ReactDOM.createRoot") || !source.includes("const App")) {
  throw new Error("LIVE JSX unexpected entrypoint; refusing unsafe build");
}
const compiled=esbuild.transformSync(source,{
  loader:"jsx",jsx:"transform",jsxFactory:"React.createElement",
  jsxFragment:"React.Fragment",format:"iife",target:"es2019",
  minify:true,legalComments:"none",charset:"utf8",sourcefile:"live.inline.jsx",
  logLevel:"warning"
});
if (!compiled.code.includes("React") || compiled.code.length<25000) throw new Error("LIVE compiled JS invalid");
fs.mkdirSync(path.dirname(target),{recursive:true});
const digest=crypto.createHash("sha256").update(compiled.code).digest("hex").slice(0,12);
fs.writeFileSync(target,"/* MrXPRONOS LIVE - generated at build time from live.html; do not edit */\n"+
                       compiled.code+"\n");
html=html.replace(match[0],'<script src="assets/js/live.precompiled.js?v='+digest+'" onerror="showBootError(\'Le module LIVE précompilé n’a pas pu être chargé\')"></script>');
html=html.replace(/^\s*<script src="https:\/\/unpkg\.com\/@babel\/standalone\/babel\.min\.js"[^>]*><\/script>\s*\r?\n/m,"\n");
if (html.includes('type="text/babel"') || html.includes("@babel/standalone")) {
  throw new Error("LIVE Babel runtime still referenced");
}
fs.writeFileSync(htmlPath,html);
console.log(JSON.stringify({status:"LIVE_PRECOMPILED",characters:source.length,bytes:compiled.code.length,digest}));
