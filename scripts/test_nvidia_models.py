#!/usr/bin/env python3
"""Banc de test NVIDIA NIM : inventaire, disponibilité et latence des modèles.

Usage : NVIDIA_API_KEY=... python scripts/test_nvidia_models.py
Aucune clé, aucun header d'authentification ni réponse complète n'est enregistré.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

from nvidia_extra_models import SPECIAL_MODELS, category_for, probe_special

BASE = "https://integrate.api.nvidia.com/v1"
RETRIEVAL = "https://ai.api.nvidia.com/v1/retrieval/nvidia"
FIELDS = [
    "model", "type", "status", "http_status", "tests", "successes",
    "avg_seconds", "min_seconds", "max_seconds", "median_seconds",
    "input_tokens", "output_tokens", "error", "answer_preview",
]


def model_type(model_id: str) -> str:
    """Type probable : le catalogue /models ne fournit pas toujours la capacité."""
    override = category_for(model_id)
    if override:
        return override
    name = model_id.lower()
    if "rerank" in name or "reranking" in name:
        return "rerank"
    if any(x in name for x in ("embed", "embedding", "bge-", "arctic-embed")):
        return "embedding"
    if any(x in name for x in (
        "whisper", "transcrib", "speech", "tts", "asr", "audio-", "riva-",
        "parse", "segment", "imagegen", "diffusion", "flux-", "cosmos-",
    )):
        return "specialized"
    return "chat"


def sanitize(value: object) -> str:
    value = str(value or "")
    value = re.sub(r"nvapi-[A-Za-z0-9_-]+", "[MASQUÉ]", value)
    value = re.sub(r"Bearer\s+\S+", "Bearer [MASQUÉ]", value, flags=re.I)
    return " ".join(value.split())[:230]


def list_models(session: requests.Session, timeout: float) -> list[str]:
    response = session.get(BASE + "/models", timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError("Catalogue NVIDIA inaccessible (HTTP %s) : %s" %
                           (response.status_code, sanitize(response.text)))
    data = response.json().get("data", [])
    if not isinstance(data, list):
        raise ValueError("Format inattendu pour /v1/models")
    return sorted({
        item["id"].strip()
        for item in data if isinstance(item, dict)
        and isinstance(item.get("id"), str) and item["id"].strip()
    })


def requests_for(model: str, kind: str, max_tokens: int):
    """Renvoie des (url, charge utile) propres au type de modèle."""
    if kind == "chat":
        return [(BASE + "/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content": "Réponds par le seul mot OK."}],
            "max_tokens": max_tokens,
            "stream": False,
        })]
    if kind == "embedding":
        return [
            (BASE + "/embeddings", {"model": model, "input": ["Bonjour NVIDIA"], "input_type": "query"}),
            (BASE + "/embeddings", {"model": model, "input": ["Bonjour NVIDIA"]}),
            (RETRIEVAL + "/embeddings", {"model": model, "input": ["Bonjour NVIDIA"], "input_type": "query"}),
        ]
    if kind == "rerank":
        # Les rerankers exposent souvent un endpoint particulier sur ai.api.nvidia.com.
        owner, _, name = model.partition("/")
        model_path = quote(owner, safe="") + "/" + quote(name.replace(".", "_"), safe="")
        payload = {"model": model, "query": {"text": "Quelle est la capitale du Togo ?"},
                   "passages": [{"text": "Lomé est la capitale du Togo."}],
                   "truncate": "END"}
        return [
            (RETRIEVAL + "/reranking", payload),
            ("https://ai.api.nvidia.com/v1/retrieval/" + model_path + "/reranking", payload),
            (BASE + "/reranking", payload),
        ]
    # Generic fallback: attempt at least one call for an unknown specialist.
    # HTTP 400/404 here cannot establish the model is unavailable: its real API may differ.
    if kind == "specialized":
        return [(BASE + "/chat/completions", {
            "model": model, "messages": [{"role": "user", "content": "Réponds OK."}],
            "max_tokens": max_tokens, "stream": False,
        })]
    return []


def success_from_json(kind: str, body: dict) -> tuple[bool, str]:
    """HTTP 200 ne suffit pas à déclarer une réponse exploitable."""
    if not isinstance(body, dict):
        return False, ""
    if kind in ("chat", "specialized"):
        choices = body.get("choices", [])
        if not isinstance(choices, list) or not choices:
            return False, ""
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message") or {}
        text = message.get("content", "") if isinstance(message, dict) else ""
        if isinstance(text, list):
            text = " ".join(str(p.get("text", "")) for p in text if isinstance(p, dict))
        return bool(str(text or "").strip()), sanitize(text)[:120]
    if kind == "embedding":
        data = body.get("data", [])
        return bool(isinstance(data, list) and data and
                    isinstance(data[0], dict) and data[0].get("embedding")), "vecteur"
    if kind == "rerank":
        result = body.get("rankings", body.get("data", body.get("results", [])))
        return bool(isinstance(result, list) and result), "classement"
    return False, ""


def status_for(http_code: int) -> str:
    return {
        400: "requete_refusee", 401: "cle_invalide", 402: "paiement_requis",
        403: "acces_refuse", 404: "introuvable", 405: "endpoint_incompatible",
        410: "retire", 422: "requete_refusee", 429: "limite_atteinte",
    }.get(http_code, "erreur_serveur" if http_code >= 500 else "erreur_http")


def probe(session: requests.Session, model: str, kind: str,
          timeout: float, max_tokens: int) -> dict:
    if model in SPECIAL_MODELS:
        return probe_special(session, model, timeout, sanitize)
    endpoints = requests_for(model, kind, max_tokens)
    if not endpoints:
        return {"status": "api_specialisee_non_testee", "http_status": None,
                "elapsed": None, "input_tokens": 0, "output_tokens": 0,
                "error": "API dédiée nécessaire (hors protocole standard)", "preview": ""}
    last = None
    for index, (url, payload) in enumerate(endpoints):
        began = time.perf_counter()
        try:
            response = session.post(url, json=payload, timeout=timeout)
            elapsed = round(time.perf_counter() - began, 3)
            try:
                body = response.json()
            except ValueError:
                body = {}
            if response.status_code == 200:
                valid, preview = success_from_json(kind, body)
                usage = body.get("usage") or {} if isinstance(body, dict) else {}
                return {
                    "status": "ok" if valid else "reponse_vide",
                    "http_status": 200, "elapsed": elapsed,
                    "input_tokens": int(usage.get("prompt_tokens") or 0),
                    "output_tokens": int(usage.get("completion_tokens") or 0),
                    "error": "" if valid else "HTTP 200 mais aucune sortie exploitable (éventuels tokens de raisonnement uniquement)",
                    "preview": preview,
                }
            detail = body.get("detail") or body.get("error") or body.get("message") or ""
            classification = status_for(response.status_code)
            if kind == "specialized" and response.status_code in (400, 404, 405, 422):
                classification = "schema_specialise_inconnu"
            last = {"status": classification,
                    "http_status": response.status_code, "elapsed": elapsed,
                    "input_tokens": 0, "output_tokens": 0,
                    "error": sanitize(detail) or ("HTTP " + str(response.status_code)),
                    "preview": ""}
            # Ne change pas d'endpoint si la clé, le quota ou le service est en cause.
            if response.status_code in (401, 402, 403, 410, 429) or response.status_code >= 500:
                break
            # Le fallback n'est pertinent que pour les API de recherche.
            if kind == "chat" or index == len(endpoints) - 1:
                break
        except requests.Timeout:
            last = {"status": "timeout", "http_status": None,
                    "elapsed": round(time.perf_counter() - began, 3),
                    "input_tokens": 0, "output_tokens": 0,
                    "error": "Temps limite dépassé", "preview": ""}
            break
        except requests.RequestException as exc:
            last = {"status": "erreur_reseau", "http_status": None,
                    "elapsed": round(time.perf_counter() - began, 3),
                    "input_tokens": 0, "output_tokens": 0,
                    "error": sanitize(type(exc).__name__), "preview": ""}
            break
    return last or {"status": "erreur_inconnue", "http_status": None,
                    "elapsed": None, "input_tokens": 0, "output_tokens": 0,
                    "error": "Aucun résultat", "preview": ""}


def test_model(session, model: str, repeats: int, timeout: float,
               tokens: int, pause: float) -> dict:
    kind = model_type(model)
    trials = []
    for i in range(repeats if kind != "specialized" else 1):
        if i:
            time.sleep(pause)
        item = probe(session, model, kind, timeout, tokens)
        trials.append(item)
        if item["status"] not in ("ok", "reponse_vide"):
            break  # Une erreur n'est pas masquée par des essais répétés.
    timings = [t["elapsed"] for t in trials if t["elapsed"] is not None]
    successes = [t for t in trials if t["status"] == "ok"]
    last = trials[-1]
    return {
        "model": model, "type": kind,
        "status": ("ok" if len(successes) == repeats else last["status"]),
        "http_status": last["http_status"], "tests": len(trials),
        "successes": len(successes),
        "avg_seconds": round(statistics.mean(timings), 3) if timings else None,
        "min_seconds": min(timings) if timings else None,
        "max_seconds": max(timings) if timings else None,
        "median_seconds": round(statistics.median(timings), 3) if timings else None,
        "input_tokens": sum(t["input_tokens"] for t in trials),
        "output_tokens": sum(t["output_tokens"] for t in trials),
        "error": last["error"], "answer_preview": last["preview"],
    }


def save_reports(rows: list[dict], out: Path, discovered: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    summary = {
        "generated_utc": timestamp, "discovered_models": discovered,
        "tested_models": len(rows),
        "working": sum(r["status"] == "ok" for r in rows),
        "http_200_without_output": sum(r["status"] == "reponse_vide" for r in rows),
        "specialized_not_tested": sum(r["status"] == "api_specialisee_non_testee" for r in rows),
        "by_status": {s: sum(r["status"] == s for r in rows)
                      for s in sorted(set(r["status"] for r in rows))},
        "models": rows,
    }
    (out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "results.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in FIELDS} for row in rows)
    md = [
        "# NVIDIA NIM — état réel des modèles",
        "",
        "Test : " + timestamp,
        "",
        "**%s modèles découverts ; %s analysés ; %s répondent correctement.**" %
        (discovered, len(rows), summary["working"]),
        "",
        "Les erreurs 403 peuvent venir des permissions du compte ;"
        " les modèles spécialisés nécessitent une API distincte.",
        "",
        "| Modèle | Type | État | Durée moyenne (s) | HTTP |",
        "|---|---|---|---:|---:|",
    ]
    for r in sorted(rows, key=lambda r: (r["status"] != "ok", r["avg_seconds"] or 999999)):
        model = r["model"].replace("|", "/")
        md.append("| %s | %s | %s | %s | %s |" % (
            model, r["type"], r["status"],
            r["avg_seconds"] if r["avg_seconds"] is not None else "—",
            r["http_status"] or "—"))
    (out / "rapport.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as file:
            file.write("\n".join(md) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Teste les modèles NVIDIA un par un.")
    parser.add_argument("--repeats", type=int, default=1, choices=(1, 2, 3))
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=35)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--limit", type=int, default=0, help="0 = tous")
    parser.add_argument("--category", choices=("all", "chat", "embedding", "rerank", "image", "video", "vision", "document", "specialized"), default="all")
    parser.add_argument("--catalog-only", action="store_true", help="Ne pas ajouter les modèles spécialisés documentés")
    parser.add_argument("--models", default="", help="IDs exacts séparés par des virgules")
    parser.add_argument("--out", default="reports/nvidia-models")
    args = parser.parse_args(argv)
    if args.delay < 0 or args.timeout <= 0 or args.limit < 0 or args.max_tokens < 1:
        parser.error("Valeurs d'intervalle, timeout, limite ou tokens invalides")
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key:
        print("Erreur : secret NVIDIA_API_KEY absent.", file=sys.stderr)
        return 2
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        models = list_models(session, args.timeout)
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print("Erreur de découverte : " + sanitize(exc), file=sys.stderr)
        return 2
    listed = len(models)
    if not args.catalog_only and not args.models.strip():
        models = sorted(set(models) | set(SPECIAL_MODELS))
    discovered = len(models)
    print(f"Catalogue API: {listed} modèles ; catalogue spécialisé: {len(SPECIAL_MODELS)} IDs connus ; union: {discovered}.", flush=True)
    if args.models.strip():
        # Les IDs demandés peuvent être absents du catalogue : les tester quand même.
        models = sorted({m.strip() for m in args.models.split(",") if m.strip()})
    if args.category != "all":
        models = [m for m in models if model_type(m) == args.category]
    if args.limit:
        models = models[:args.limit]
    print("NVIDIA : %s modèles détectés, %s à analyser." % (discovered, len(models)), flush=True)
    results = []
    try:
        for i, model in enumerate(models, start=1):
            if i > 1:
                time.sleep(args.delay)
            result = test_model(session, model, args.repeats, args.timeout,
                                args.max_tokens, args.delay)
            results.append(result)
            print("[%s/%s] %s : %s (%s s) HTTP %s" % (
                i, len(models), model, result["status"],
                result["avg_seconds"], result["http_status"]), flush=True)
    except KeyboardInterrupt:
        print("Arrêt : rapports partiels conservés.", file=sys.stderr)
    finally:
        save_reports(results, Path(args.out), discovered)
        session.close()
    print("Rapports : %s/{results.json,results.csv,rapport.md}" % args.out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
