#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Segmenta um KML em vários KMLs, um por Placemark (setor).
Preserva name, ExtendedData, styleUrl e geometria.

Uso:
    python segmenta_setores_kml.py --input /caminho/para/seu.kml --outdir /caminho/saida

Dicas:
- Se o arquivo tiver muitos estilos globais, os novos KMLs manterão o styleUrl
  do Placemark; renderizadores costumam aceitar mesmo sem o style definido localmente.
- Os nomes dos arquivos priorizam chaves comuns em ExtendedData (CD_GEOCODI, etc.).
"""

import argparse
import os
import re
from xml.etree import ElementTree as ET

NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}

def sanitize_filename(name: str) -> str:
    name = (name or "").strip()
    # substitui qualquer caractere não alfanumérico/underscore/hífen/ponto por "_"
    name = re.sub(r"[^\w\s\-\.]", "_", name, flags=re.UNICODE)
    # troca espaços por underscore
    name = re.sub(r"\s+", "_", name)
    # limita tamanho para evitar problemas de FS
    return name[:180] or "setor"

def kml_header() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2" '
        'xmlns:gx="http://www.google.com/kml/ext/2.2" '
        'xmlns:kml="http://www.opengis.net/kml/2.2" '
        'xmlns:atom="http://www.w3.org/2005/Atom">\n'
    )

def wrap_document(inner: str) -> str:
    return f"{kml_header()}<Document>\n{inner}\n</Document>\n</kml>\n"

def has_geometry(pm: ET.Element) -> bool:
    # Considera Polygon, MultiGeometry (com Polygon), LineString, Point
    return any([
        pm.find(".//kml:Polygon", NS) is not None,
        pm.find(".//kml:MultiGeometry/kml:Polygon", NS) is not None,
        pm.find(".//kml:MultiGeometry/kml:LineString", NS) is not None,
        pm.find(".//kml:MultiGeometry/kml:Point", NS) is not None,
        pm.find(".//kml:LineString", NS) is not None,
        pm.find(".//kml:Point", NS) is not None,
    ])

def preferred_name(pm: ET.Element) -> str:
    # 1) tenta ExtendedData com chaves comuns
    ext = pm.find("kml:ExtendedData", NS)
    preferred_keys = [
        "CD_GEOCODI", "CD_GEOCOD", "SETOR", "SETOR_CENSITARIO",
        "NOME", "NAME", "NM_SETOR", "CD_SETOR", "GEOCODIGO", "CODIGO"
    ]
    if ext is not None:
        for data in ext.findall(".//kml:Data", NS):
            key = (data.get("name") or "").upper()
            val_el = data.find("kml:value", NS)
            val = (val_el.text.strip() if (val_el is not None and val_el.text) else "")
            if key in preferred_keys and val:
                return val
        # Também cobre SchemaData (menos comum)
        for sd in ext.findall(".//kml:SchemaData", NS):
            for simple in sd.findall(".//kml:SimpleData", NS):
                key = (simple.get("name") or "").upper()
                val = (simple.text or "").strip()
                if key in preferred_keys and val:
                    return val
    # 2) fallback: kml:name do Placemark
    name_el = pm.find("kml:name", NS)
    if name_el is not None and name_el.text:
        return name_el.text.strip()
    return "setor"

def segment_kml(input_path: str, outdir: str) -> int:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

    os.makedirs(outdir, exist_ok=True)

    ET.register_namespace("", NS["kml"])
    ET.register_namespace("gx", NS["gx"])

    tree = ET.parse(input_path)
    root = tree.getroot()

    placemarks = root.findall(".//kml:Placemark", NS)
    total = 0

    for pm in placemarks:
        if not has_geometry(pm):
            continue

        name = preferred_name(pm)
        file_name = sanitize_filename(name) + ".kml"
        out_path = os.path.join(outdir, file_name)

        # Clona o Placemark (para não alterar a árvore original)
        pm_copy = ET.fromstring(ET.tostring(pm, encoding="utf-8"))

        # Garante que <name> exista e reflita o nome final
        name_copy = pm_copy.find("kml:name", NS)
        if name_copy is None:
            name_copy = ET.SubElement(pm_copy, f"{{{NS['kml']}}}name")
        name_copy.text = name

        # Serializa e embrulha em um Document
        pm_str = ET.tostring(pm_copy, encoding="unicode")
        kml_final = wrap_document(pm_str)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(kml_final)

        total += 1

    return total

def main():
    parser = argparse.ArgumentParser(description="Segmenta setores censitários de um KML em vários KMLs (um por Placemark).")
    parser.add_argument("--input", "-i", required=True, help="Caminho para o arquivo KML de entrada.")
    parser.add_argument("--outdir", "-o", required=True, help="Diretório de saída para os KMLs segmentados.")
    args = parser.parse_args()

    count = segment_kml(args.input, args.outdir)
    print(f"Concluído. {count} arquivo(s) KML gerado(s) em: {args.outdir}")

if __name__ == "__main__":
    main()
