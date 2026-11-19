#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Strict Spectre 15.1 PSF ASCII state-machine reader; Python 2.6.6+ and Python 3 stdlib only.

Supports full PSF ASCII sections:
- HEADER (metadata key-value pairs)
- TYPE (scalar, COMPLEX, ARRAY, and multi-field / nested STRUCT definitions)
- SWEEP (independent sweep variable declarations: time, freq, dc, param)
- TRACE (dependent trace declarations including `" 401" GROUP N` signal mappings)
- VALUE (scalar real/int, complex `(re im)`, multi-line STRUCT instance tuples
  `"M1" "bsim4" ( ... ) PROP(...)`, and step-hold delta-compressed swept records)

Rejects NaN/Inf values in numeric signals and writes zero bytecode inside library/tools/.
"""
from __future__ import division, print_function

import json
import math
import os
from optparse import OptionParser
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

try:
    _INT_TYPES = (int, long)  # noqa: F821
except NameError:
    _INT_TYPES = (int,)
_NUM_TYPES = _INT_TYPES + (float,)
try:
    _TEXT_TYPES = (basestring,)  # noqa: F821
except NameError:
    _TEXT_TYPES = (str,)

_SECTION_KEYWORDS = set(["HEADER", "TYPE", "SWEEP", "TRACE", "VALUE", "END"])
_KIND_KEYWORDS = set([
    "FLOAT", "DOUBLE", "COMPLEX", "INT", "BYTE", "LONG", "SINGLE", "STRING", "KEY"
])

_TOKEN_RE = re.compile(
    r'\s*(?:'
    r'"((?:[^"\\]|\\.)*)"'
    r'|([()*])'
    r'|([+-]?(?:(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?|[nN][aA][nN]|[iI][nN][fF]))'
    r'|([A-Za-z_][A-Za-z0-9_]*)'
    r')'
)
_WS_RE = re.compile(r'\s*')


def _unescape_psf_string(raw):
    if "\\" not in raw:
        return raw
    return re.sub(r'\\(.)', r'\1', raw)


def _check_finite(scalar, name):
    if math.isnan(scalar) or math.isinf(scalar):
        raise ValueError("Non-finite PSF value for signal %s" % name)


def _tokenize_psf(content, path):
    tokens = []
    pos = 0
    total = len(content)
    while pos < total:
        ws = _WS_RE.match(content, pos)
        if ws:
            pos = ws.end()
        if pos >= total:
            break
        match = _TOKEN_RE.match(content, pos)
        if not match or match.end() == pos:
            snippet = content[pos:pos + 40].splitlines()[0]
            raise ValueError(
                "Unsupported PSF syntax in %s at offset %d: %s" % (path, pos, snippet)
            )
        s_tok, p_tok, n_tok, kw_tok = match.groups()
        if s_tok is not None:
            tokens.append(("STR", _unescape_psf_string(s_tok)))
        elif p_tok is not None:
            if p_tok == "(":
                tokens.append(("LPAREN", "("))
            elif p_tok == ")":
                tokens.append(("RPAREN", ")"))
            else:
                tokens.append(("STAR", "*"))
        elif n_tok is not None:
            tokens.append(("NUM", n_tok))
        else:
            tokens.append(("KW", kw_tok))
        pos = match.end()
    return tokens


def _parse_scalar_token(raw_num, as_int=False):
    low = raw_num.lower()
    if low in ("nan", "+nan", "-nan"):
        return float("nan")
    if low in ("inf", "+inf"):
        return float("inf")
    if low == "-inf":
        return float("-inf")
    if as_int and ("." not in raw_num and "e" not in low):
        return int(raw_num)
    return float(raw_num)


def _parse_prop_block(tokens, idx):
    """Parse PROP( ... ) starting with idx at ('KW', 'PROP')."""
    n = len(tokens)
    props = {}
    if idx >= n or tokens[idx] != ("KW", "PROP"):
        return props, idx
    idx += 1
    if idx >= n or tokens[idx][0] != "LPAREN":
        raise ValueError("Expected '(' after PROP in PSF file")
    idx += 1
    depth = 1
    while idx < n and depth > 0:
        ttype, tval = tokens[idx]
        if ttype == "LPAREN":
            depth += 1
            idx += 1
        elif ttype == "RPAREN":
            depth -= 1
            idx += 1
        elif depth == 1 and ttype == "STR" and idx + 1 < n and tokens[idx + 1][0] in ("STR", "NUM"):
            vtype, vraw = tokens[idx + 1]
            if vtype == "STR":
                props[tval] = vraw
            else:
                if "." in vraw or "e" in vraw.lower() or "n" in vraw.lower() or "i" in vraw.lower():
                    props[tval] = _parse_scalar_token(vraw, as_int=False)
                else:
                    props[tval] = int(vraw)
            idx += 2
        else:
            idx += 1
    return props, idx


def _parse_type_declarations(tokens, idx, stop_at_rparen=False, known_types=None):
    """Parse TYPE entries or STRUCT( ... ) member declarations."""
    n = len(tokens)
    decls = []
    local_known = dict(known_types) if known_types else {}
    while idx < n:
        ttype, tval = tokens[idx]
        if stop_at_rparen and ttype == "RPAREN":
            idx += 1
            break
        if not stop_at_rparen and ttype == "KW" and tval in _SECTION_KEYWORDS:
            break
        if ttype != "STR":
            raise ValueError("Expected quoted type/member name in TYPE section, got %s" % repr(tokens[idx]))
        name = tval
        idx += 1
        kinds = []
        sub_struct = None
        props = {}
        is_array = False
        ref_type = None
        while idx < n:
            ktype, kval = tokens[idx]
            if ktype == "RPAREN" and stop_at_rparen:
                break
            if ktype == "KW" and kval in _SECTION_KEYWORDS and not stop_at_rparen:
                break
            if ktype == "STR":
                if not kinds and sub_struct is None and ref_type is None:
                    ref_type = kval
                    idx += 1
                    if ref_type in local_known:
                        ref_decl = local_known[ref_type]
                        if ref_decl.get("kind"):
                            kinds.extend(ref_decl["kind"].split())
                        if ref_decl.get("struct") is not None:
                            sub_struct = ref_decl["struct"]
                        if ref_decl.get("array"):
                            is_array = True
                        if ref_decl.get("props"):
                            merged_p = dict(ref_decl["props"])
                            merged_p.update(props)
                            props = merged_p
                    continue
                break
            if ktype == "KW" and kval == "PROP":
                p_dict, idx = _parse_prop_block(tokens, idx)
                props.update(p_dict)
            elif ktype == "KW" and kval == "STRUCT":
                idx += 1
                if idx >= n or tokens[idx][0] != "LPAREN":
                    raise ValueError("Expected '(' after STRUCT for type %s" % name)
                idx += 1
                sub_struct, idx = _parse_type_declarations(
                    tokens, idx, stop_at_rparen=True, known_types=local_known
                )
                kinds.append("struct")
            elif ktype == "KW" and kval == "ARRAY":
                is_array = True
                idx += 1
                if idx < n and tokens[idx][0] == "LPAREN":
                    depth = 1
                    idx += 1
                    while idx < n and depth > 0:
                        if tokens[idx][0] == "LPAREN":
                            depth += 1
                        elif tokens[idx][0] == "RPAREN":
                            depth -= 1
                        idx += 1
                kinds.append("array")
            elif ktype == "STAR":
                kinds.append("*")
                idx += 1
            elif ktype == "KW":
                kinds.append(kval.lower())
                idx += 1
            else:
                idx += 1
        decl_obj = {
            "name": name,
            "kind": " ".join(kinds),
            "ref_type": ref_type,
            "struct": sub_struct,
            "array": is_array,
            "props": props,
        }
        decls.append(decl_obj)
        local_known[name] = decl_obj
        if not stop_at_rparen and known_types is not None:
            known_types[name] = decl_obj
    return decls, idx


def _consume_trailing_props(tokens, idx):
    merged = {}
    n = len(tokens)
    while idx < n and tokens[idx] == ("KW", "PROP"):
        p_dict, idx = _parse_prop_block(tokens, idx)
        merged.update(p_dict)
    return merged, idx


def _parse_value_atom(tokens, idx, signal_name, reject_nonfinite=True, as_int=False):
    """Parse one numeric scalar, complex `(re im)`, or string value atom."""
    n = len(tokens)
    if idx >= n:
        raise ValueError("Unexpected EOF while reading value for %s" % signal_name)
    ttype, tval = tokens[idx]
    if ttype == "NUM":
        val = _parse_scalar_token(tval, as_int=as_int)
        if reject_nonfinite:
            _check_finite(float(val), signal_name)
        idx += 1
        props, idx = _consume_trailing_props(tokens, idx)
        return ("num", val, props), idx
    if ttype == "STR":
        idx += 1
        props, idx = _consume_trailing_props(tokens, idx)
        return ("str", tval, props), idx
    if ttype == "LPAREN":
        # Complex pair `(re im)` or nested tuple
        idx += 1
        items = []
        while idx < n and tokens[idx][0] != "RPAREN":
            sub_atom, idx = _parse_value_atom(tokens, idx, signal_name, reject_nonfinite=reject_nonfinite)
            items.append(sub_atom)
        if idx >= n or tokens[idx][0] != "RPAREN":
            raise ValueError("Unclosed '(' for signal %s" % signal_name)
        idx += 1
        props, idx = _consume_trailing_props(tokens, idx)
        if len(items) == 2 and items[0][0] == "num" and items[1][0] == "num":
            cval = complex(float(items[0][1]), float(items[1][1]))
            return ("complex", cval, props), idx
        return ("tuple", [it[1] for it in items], props), idx
    raise ValueError("Unsupported PSF VALUE token %s for signal %s" % (repr(tokens[idx]), signal_name))


def _parse_struct_instance(tokens, idx, inst_name, struct_def, reject_nonfinite=True):
    """Parse `( v1 v2 ... ) [PROP(...)]` against a TYPE STRUCT definition."""
    n = len(tokens)
    if idx >= n or tokens[idx][0] != "LPAREN":
        raise ValueError("Expected '(' for STRUCT instance %s" % inst_name)
    idx += 1
    fields = struct_def.get("struct") or []
    field_idx = 0
    out_fields = {}
    field_order = []
    flat_scalars = []
    field_units = {}
    raw_items = []

    while idx < n and tokens[idx][0] != "RPAREN":
        if field_idx < len(fields):
            f_meta = fields[field_idx]
            f_name = f_meta["name"]
            f_kind = f_meta.get("kind", "")
            full_name = "%s:%s" % (inst_name, f_name)
            f_unit = f_meta.get("props", {}).get("units")
            if f_unit:
                field_units[full_name] = f_unit
            if f_meta.get("struct") is not None and tokens[idx][0] == "LPAREN":
                nested_obj, idx = _parse_struct_instance(
                    tokens, idx, full_name, f_meta, reject_nonfinite=reject_nonfinite
                )
                out_fields[f_name] = nested_obj["fields"]
                field_order.append(f_name)
                flat_scalars.extend(nested_obj.get("flat_scalars", []))
                field_units.update(nested_obj.get("field_units", {}))
                field_idx += 1
                continue
            want_int = ("int" in f_kind) and ("float" not in f_kind) and ("double" not in f_kind)
            atom, idx = _parse_value_atom(
                tokens, idx, full_name, reject_nonfinite=reject_nonfinite, as_int=want_int
            )
            out_fields[f_name] = atom[1]
            field_order.append(f_name)
            flat_scalars.append((full_name, atom[1]))
        else:
            atom, idx = _parse_value_atom(
                tokens, idx, inst_name, reject_nonfinite=reject_nonfinite, as_int=False
            )
            raw_items.append(atom[1])
            flat_scalars.append(("%s:extra_%d" % (inst_name, len(raw_items) - 1), atom[1]))
        field_idx += 1

    if idx >= n or tokens[idx][0] != "RPAREN":
        raise ValueError("Unclosed STRUCT '(' for instance %s" % inst_name)
    idx += 1
    props, idx = _consume_trailing_props(tokens, idx)
    return {
        "type": struct_def["name"],
        "fields": out_fields,
        "field_order": field_order,
        "flat_scalars": flat_scalars,
        "field_units": field_units,
        "extra": raw_items,
        "props": props,
    }, idx


def _wanted_match(name, wanted):
    if wanted is None:
        return True
    if name in wanted:
        return True
    if ":" in name:
        inst, param = name.split(":", 1)
        if inst in wanted or ("%s.%s" % (inst, param)) in wanted:
            return True
    return False


def parse_psf_file(
    path,
    names=None,
    reject_nonfinite=True,
    reject_truncated=True,
    fill_leading_missing=True,
):
    """Full state-machine parser for Spectre 15.1 PSF ASCII files.

    Returns a dictionary containing:
      header, types, sweeps, traces, trace_types, groups, values, instances,
      strings, field_units, backfilled_leading_signals, sweep_name, sweep_values,
      has_value_section
    """
    wanted = set(names) if names is not None else None

    stream = open(path, "rb")
    try:
        content = stream.read().decode("latin1")
    finally:
        stream.close()

    tokens = _tokenize_psf(content, path)
    n = len(tokens)
    idx = 0

    header = {}
    types = {}
    sweeps = []
    traces = []
    trace_types = {}
    groups = {}
    trace_order = []
    trace_seen = set()
    instances = {}
    strings = {}
    values = {}
    field_units = {}
    unit_conflicts = {}
    sample_units_seen = {}
    backfilled_leading_signals = {}
    has_value_section = False
    saw_value_end = False

    while idx < n:
        ttype, tval = tokens[idx]
        if ttype != "KW" or tval not in _SECTION_KEYWORDS:
            raise ValueError("Expected PSF section keyword in %s, got %s" % (path, repr(tokens[idx])))

        section = tval
        idx += 1

        if section == "END":
            break

        if section == "HEADER":
            while idx < n:
                if tokens[idx][0] == "KW" and tokens[idx][1] in _SECTION_KEYWORDS:
                    break
                if tokens[idx][0] != "STR" or idx + 1 >= n:
                    raise ValueError("Malformed HEADER entry in %s" % path)
                h_key = tokens[idx][1]
                idx += 1
                v_type, v_raw = tokens[idx]
                if v_type == "STR":
                    header[h_key] = v_raw
                    idx += 1
                elif v_type == "NUM":
                    if "." in v_raw or "e" in v_raw.lower() or "n" in v_raw.lower() or "i" in v_raw.lower():
                        header[h_key] = _parse_scalar_token(v_raw, as_int=False)
                    else:
                        header[h_key] = int(v_raw)
                    idx += 1
                else:
                    header[h_key] = v_raw
                    idx += 1
                _, idx = _consume_trailing_props(tokens, idx)

        elif section == "TYPE":
            decls, idx = _parse_type_declarations(tokens, idx, stop_at_rparen=False, known_types=types)
            for d in decls:
                types[d["name"]] = d

        elif section == "SWEEP":
            while idx < n:
                if tokens[idx][0] == "KW" and tokens[idx][1] in _SECTION_KEYWORDS:
                    break
                if tokens[idx][0] != "STR":
                    raise ValueError("Expected sweep variable name in %s" % path)
                sw_name = tokens[idx][1]
                idx += 1
                sw_type = ""
                if idx < n and tokens[idx][0] == "STR":
                    sw_type = tokens[idx][1]
                    idx += 1
                while idx < n and tokens[idx][0] == "KW" and tokens[idx][1] in _KIND_KEYWORDS:
                    idx += 1
                sw_props, idx = _consume_trailing_props(tokens, idx)
                sweeps.append({"name": sw_name, "type": sw_type, "props": sw_props})
                if sw_props.get("units"):
                    field_units[sw_name] = sw_props["units"]
                elif sw_type in types and types[sw_type].get("props", {}).get("units"):
                    field_units[sw_name] = types[sw_type]["props"]["units"]

        elif section == "TRACE":
            while idx < n:
                if tokens[idx][0] == "KW" and tokens[idx][1] in _SECTION_KEYWORDS:
                    break
                if tokens[idx][0] != "STR":
                    raise ValueError("Expected trace name or group ID in %s" % path)
                tr_name = tokens[idx][1]
                idx += 1
                if idx < n and tokens[idx] == ("KW", "GROUP"):
                    idx += 1
                    if idx >= n or tokens[idx][0] != "NUM":
                        raise ValueError("Expected integer count after GROUP in %s" % path)
                    g_count = int(tokens[idx][1])
                    idx += 1
                    _, idx = _consume_trailing_props(tokens, idx)
                    members = []
                    for _ in range(g_count):
                        if idx >= n or tokens[idx][0] != "STR":
                            raise ValueError("Expected group member trace name in %s" % path)
                        m_name = tokens[idx][1]
                        idx += 1
                        m_type = ""
                        if idx < n and tokens[idx][0] == "STR":
                            m_type = tokens[idx][1]
                            idx += 1
                        m_props, idx = _consume_trailing_props(tokens, idx)
                        members.append(m_name)
                        trace_types[m_name] = m_type
                        if m_props.get("units"):
                            field_units[m_name] = m_props["units"]
                        elif m_type in types and types[m_type].get("props", {}).get("units"):
                            field_units[m_name] = types[m_type]["props"]["units"]
                        traces.append({"name": m_name, "type": m_type, "group": tr_name, "props": m_props})
                        if m_name not in trace_seen:
                            trace_seen.add(m_name)
                            trace_order.append(m_name)
                    groups[tr_name] = members
                else:
                    tr_type = ""
                    if idx < n and tokens[idx][0] == "STR":
                        tr_type = tokens[idx][1]
                        idx += 1
                    tr_props, idx = _consume_trailing_props(tokens, idx)
                    trace_types[tr_name] = tr_type
                    if tr_props.get("units"):
                        field_units[tr_name] = tr_props["units"]
                    elif tr_type in types and types[tr_type].get("props", {}).get("units"):
                        field_units[tr_name] = types[tr_type]["props"]["units"]
                    traces.append({"name": tr_name, "type": tr_type, "group": None, "props": tr_props})
                    if tr_name not in trace_seen:
                        trace_seen.add(tr_name)
                        trace_order.append(tr_name)

        elif section == "VALUE":
            has_value_section = True
            sweep_name = sweeps[0]["name"] if sweeps else None
            swept_events = []
            base_field_units = dict(field_units)

            def _record_sample_unit(sig_name, explicit_unit, inline_type=None):
                if explicit_unit:
                    u_eff = str(explicit_unit).strip()
                    field_units[sig_name] = u_eff
                else:
                    t_u = ""
                    if inline_type and inline_type in types:
                        t_u = str(types[inline_type].get("props", {}).get("units") or "").strip()
                    u_eff = t_u or str(base_field_units.get(sig_name, "")).strip()
                if sig_name in sample_units_seen:
                    prev_u = sample_units_seen[sig_name]
                    if prev_u != u_eff:
                        bucket = unit_conflicts.setdefault(sig_name, [prev_u])
                        if u_eff not in bucket:
                            bucket.append(u_eff)
                else:
                    sample_units_seen[sig_name] = u_eff

            def _record_scalar(sig_name, val):
                if sweep_name is not None:
                    if sig_name != sweep_name and sig_name not in trace_seen:
                        trace_seen.add(sig_name)
                        trace_order.append(sig_name)
                    swept_events.append((sig_name, val))
                elif _wanted_match(sig_name, wanted):
                    values.setdefault(sig_name, []).append(val)

            def _record_struct(inst_key, inst_obj):
                instances[inst_key] = inst_obj
                field_units.update(inst_obj.get("field_units", {}))
                for flat_key, f_val in inst_obj.get("flat_scalars", []):
                    if isinstance(f_val, _NUM_TYPES + (complex,)) and not isinstance(f_val, bool):
                        _record_scalar(flat_key, f_val)
                    elif isinstance(f_val, _TEXT_TYPES):
                        strings[flat_key] = f_val

            while idx < n:
                if tokens[idx] == ("KW", "END"):
                    saw_value_end = True
                    break
                if tokens[idx][0] != "STR":
                    raise ValueError(
                        "Unsupported PSF VALUE token in %s: %s" % (path, repr(tokens[idx]))
                    )
                raw_key = tokens[idx][1]
                idx += 1

                # Case 1: GROUP trace vector `" 401" <v1> ... <vN>` (supports STRUCT members)
                if raw_key in groups:
                    members = groups[raw_key]
                    for m_name in members:
                        m_type = trace_types.get(m_name)
                        if (
                            m_type is not None
                            and m_type in types
                            and types[m_type].get("struct") is not None
                            and idx < n
                            and tokens[idx][0] == "LPAREN"
                        ):
                            inst_obj, idx = _parse_struct_instance(
                                tokens, idx, m_name, types[m_type], reject_nonfinite=reject_nonfinite
                            )
                            _record_struct(m_name, inst_obj)
                            continue
                        atom, idx = _parse_value_atom(
                            tokens, idx, m_name, reject_nonfinite=reject_nonfinite
                        )
                        _record_sample_unit(m_name, atom[2].get("units"), inline_type=m_type)
                        if atom[0] in ("num", "complex"):
                            _record_scalar(m_name, atom[1])
                        elif atom[0] == "tuple":
                            for pos_i, item_val in enumerate(atom[1]):
                                if isinstance(item_val, _NUM_TYPES + (complex,)) and not isinstance(item_val, bool):
                                    _record_scalar("%s:field_%d" % (m_name, pos_i), item_val)
                        elif atom[0] == "str":
                            strings[m_name] = atom[1]
                    continue

                # Optional inline type name token `"V"`, `"A"`, `"bsim4"`, etc.
                type_tag = None
                if idx + 1 < n and tokens[idx][0] == "STR":
                    cand_tag = tokens[idx][1]
                    next_tt = tokens[idx + 1][0]
                    is_struct_tag = (cand_tag in types) and (types[cand_tag].get("struct") is not None)
                    declared_t = trace_types.get(raw_key)
                    is_declared_string = False
                    if declared_t:
                        dt_low = declared_t.lower()
                        if dt_low in ("string", "str") or "string" in types.get(declared_t, {}).get("kind", ""):
                            is_declared_string = True
                    if next_tt in ("NUM", "LPAREN"):
                        if not (is_struct_tag and next_tt != "LPAREN"):
                            type_tag = cand_tag
                            idx += 1
                    elif next_tt == "STR":
                        is_known_tag = (cand_tag in types) or (cand_tag.lower() in ("string", "str"))
                        has_following_val = (idx + 2 < n and tokens[idx + 2][0] in ("NUM", "LPAREN"))
                        if (
                            is_known_tag
                            and (not is_struct_tag)
                            and (not is_declared_string)
                            and not (raw_key in trace_types and has_following_val)
                        ):
                            type_tag = cand_tag
                            idx += 1

                effective_type = type_tag if type_tag is not None else trace_types.get(raw_key)
                if effective_type and effective_type in types and types[effective_type].get("props", {}).get("units"):
                    field_units.setdefault(raw_key, types[effective_type]["props"]["units"])

                # Case 2: STRUCT instance (`"M1" "bsim4" ( ... )` or TRACE-typed `"mn.m1" ( ... )`)
                if (
                    effective_type is not None
                    and effective_type in types
                    and types[effective_type].get("struct") is not None
                    and idx < n
                    and tokens[idx][0] == "LPAREN"
                ):
                    inst_obj, idx = _parse_struct_instance(
                        tokens, idx, raw_key, types[effective_type], reject_nonfinite=reject_nonfinite
                    )
                    _record_struct(raw_key, inst_obj)
                    continue

                # Case 3: Complex pair `(re im)` or unregistered multi-element STRUCT tuple `(v0 v1 ...)`
                if idx < n and tokens[idx][0] == "LPAREN":
                    atom, idx = _parse_value_atom(
                        tokens, idx, raw_key, reject_nonfinite=reject_nonfinite
                    )
                    _record_sample_unit(raw_key, atom[2].get("units"), inline_type=effective_type)
                    if atom[0] == "complex":
                        _record_scalar(raw_key, atom[1])
                    elif atom[0] == "tuple":
                        inst_fields = {}
                        f_order = []
                        flat_sc = []
                        for pos_i, item_val in enumerate(atom[1]):
                            fn = "field_%d" % pos_i
                            inst_fields[fn] = item_val
                            f_order.append(fn)
                            flat_sc.append(("%s:%s" % (raw_key, fn), item_val))
                        _record_struct(
                            raw_key,
                            {
                                "type": effective_type or "tuple",
                                "fields": inst_fields,
                                "field_order": f_order,
                                "flat_scalars": flat_sc,
                                "field_units": {},
                                "extra": [],
                                "props": atom[2],
                            },
                        )
                    continue

                # Case 4: Standard scalar / string value
                type_tag = types.get(effective_type, {}) if effective_type else {}
                want_int = (
                    ("int" in type_tag.get("kind", ""))
                    and ("float" not in type_tag.get("kind", ""))
                    and ("double" not in type_tag.get("kind", ""))
                )
                atom, idx = _parse_value_atom(
                    tokens, idx, raw_key, reject_nonfinite=reject_nonfinite, as_int=want_int
                )
                _record_sample_unit(raw_key, atom[2].get("units"), inline_type=effective_type)
                if atom[0] in ("num", "complex"):
                    _record_scalar(raw_key, atom[1])
                elif atom[0] == "str":
                    strings[raw_key] = atom[1]

            if reject_truncated and not saw_value_end:
                raise ValueError(
                    "Truncated PSF ASCII file (missing closing END in VALUE section): " + path
                )

            # Step-hold delta decompression for swept PSF files
            if sweep_name is not None and swept_events:
                sweep_values = []
                state = {}
                first_seen = {}
                series = dict((nm, []) for nm in trace_order)
                missing_slots = dict((nm, []) for nm in trace_order)
                trailing_sweep = (swept_events[0][0] != sweep_name)

                if not trailing_sweep:
                    for ev_key, ev_val in swept_events:
                        if ev_key == sweep_name:
                            if sweep_values:
                                step_idx = len(sweep_values) - 1
                                for nm in trace_order:
                                    if nm in state:
                                        series[nm].append(state[nm])
                                    else:
                                        series[nm].append(None)
                                        missing_slots[nm].append(step_idx)
                            sweep_values.append(ev_val)
                        else:
                            state[ev_key] = ev_val
                            if ev_key not in first_seen:
                                first_seen[ev_key] = ev_val
                    if sweep_values:
                        step_idx = len(sweep_values) - 1
                        for nm in trace_order:
                            if nm in state:
                                series[nm].append(state[nm])
                            else:
                                series[nm].append(None)
                                missing_slots[nm].append(step_idx)
                else:
                    for ev_key, ev_val in swept_events:
                        if ev_key == sweep_name:
                            sweep_values.append(ev_val)
                            step_idx = len(sweep_values) - 1
                            for nm in trace_order:
                                if nm in state:
                                    series[nm].append(state[nm])
                                else:
                                    series[nm].append(None)
                                    missing_slots[nm].append(step_idx)
                        else:
                            state[ev_key] = ev_val
                            if ev_key not in first_seen:
                                first_seen[ev_key] = ev_val

                for nm in trace_order:
                    if nm in first_seen and missing_slots[nm]:
                        backfilled_leading_signals[nm] = len(missing_slots[nm])
                        if fill_leading_missing:
                            fill_val = first_seen[nm]
                            for slot in missing_slots[nm]:
                                series[nm][slot] = fill_val

                if sweep_values:
                    if _wanted_match(sweep_name, wanted):
                        values[sweep_name] = sweep_values
                    for nm in trace_order:
                        if nm in first_seen and _wanted_match(nm, wanted):
                            values[nm] = series[nm]
                else:
                    # Fallback if SWEEP was declared in header but sweep_name never appeared in VALUE
                    for ev_key, ev_val in swept_events:
                        if _wanted_match(ev_key, wanted):
                            values.setdefault(ev_key, []).append(ev_val)

    if reject_truncated and not has_value_section:
        raise ValueError(
            "Truncated PSF ASCII file (missing VALUE section): " + path
        )

    return {
        "header": header,
        "types": types,
        "sweeps": sweeps,
        "traces": traces,
        "trace_types": trace_types,
        "groups": groups,
        "values": values,
        "instances": instances,
        "strings": strings,
        "field_units": field_units,
        "unit_conflicts": unit_conflicts,
        "backfilled_leading_signals": backfilled_leading_signals,
        "sweep_name": sweeps[0]["name"] if sweeps else None,
        "sweep_values": values.get(sweeps[0]["name"]) if sweeps and sweeps[0]["name"] in values else None,
        "has_value_section": has_value_section,
    }


def read_psf_ascii(path, names=None):
    """Parse VALUE records from a Spectre PSF ASCII file.

    Returns dict mapping signal_name -> list of float/int or complex values.
    Preserves full backward compatibility while supporting STRUCT, SWEEP,
    TRACE GROUP mappings, and step-hold delta-compressed waveforms.
    """
    parsed = parse_psf_file(path, names=names, reject_nonfinite=True)
    if not parsed["has_value_section"]:
        raise ValueError("No VALUE section found in PSF ASCII file: " + path)
    if not parsed["values"] and names is None:
        raise ValueError("No numeric VALUE records parsed from: " + path)
    return parsed["values"]


def serialize_scalar(value):
    if isinstance(value, complex):
        mag = abs(value)
        db20 = 20.0 * math.log10(mag) if mag > 0.0 else None
        phase_deg = math.degrees(math.atan2(value.imag, value.real))
        return {
            "re": value.real,
            "im": value.imag,
            "mag": mag,
            "db20": db20,
            "phase_deg": phase_deg,
        }
    return value


def summarize_psf(values, full=False, at_index=None):
    out = {}
    for key in sorted(values.keys()):
        arr = values[key]
        if not arr:
            continue
        entry = {
            "count": len(arr),
            "complex": isinstance(arr[0], complex),
            "first": serialize_scalar(arr[0]),
            "last": serialize_scalar(arr[-1]),
        }
        if at_index is not None and -len(arr) <= at_index < len(arr):
            entry["at_index"] = serialize_scalar(arr[at_index])
        if full:
            entry["values"] = [serialize_scalar(v) for v in arr]
        out[key] = entry
    return out


HELP_TEXT = """Usage: python tools/psf_ascii_reader.py PSF_ASCII_FILE [options]

Options:
  --signal NAME    Filter output to one or more exact PSF signal names (repeatable)
  --at-index N     Include sample at index N (e.g. 0 for DC/1Hz, -1 for final point)
  --full           Include full point array for selected signals
  --instances      Include parsed STRUCT instance dictionaries (e.g. dcOpInfo.info)
  -h, --help       Show this help text
"""


class _SilentOptionParser(OptionParser):
    def error(self, msg):
        raise ValueError(msg)


def run_self_test():
    tmp_d = tempfile.mkdtemp(prefix="psf_reader_test_")
    try:
        # 1. Truncated PSF without END must raise ValueError
        trunc_p = os.path.join(tmp_d, "truncated.tran")
        wf = open(trunc_p, "wb")
        try:
            wf.write(
                b'HEADER\nSWEEP\n"time" "s"\nTRACE\n"out" "V"\nVALUE\n"time" 0.0\n"out" 1.0\n'
            )
        finally:
            wf.close()
        caught_trunc = False
        try:
            parse_psf_file(trunc_p)
        except ValueError:
            caught_trunc = True
        if not caught_trunc:
            raise AssertionError("Truncated PSF missing END was not rejected!")

        # 2. Leading missing sweep samples must be flagged in backfilled_leading_signals & None when fill_leading_missing=False
        lead_p = os.path.join(tmp_d, "leading_gap.tran")
        wf = open(lead_p, "wb")
        try:
            wf.write(
                b'HEADER\nSWEEP\n"time" "s"\nTRACE\n"out" "V"\nVALUE\n'
                b'"time" 0.0\n"time" 1.0\n"out" 4.0\n"time" 2.0\n"out" 5.0\nEND\n'
            )
        finally:
            wf.close()
        p_def = parse_psf_file(lead_p, fill_leading_missing=True)
        if p_def["backfilled_leading_signals"] != {"out": 1}:
            raise AssertionError("Expected backfilled_leading_signals={'out': 1}, got %r" % p_def["backfilled_leading_signals"])
        p_strict = parse_psf_file(lead_p, fill_leading_missing=False)
        if p_strict["values"]["out"] != [None, 4.0, 5.0]:
            raise AssertionError("Expected [None, 4.0, 5.0] with fill_leading_missing=False, got %r" % p_strict["values"]["out"])

        # 3. Swept STRUCT + TRACE GROUP noise contributors
        ns_p = os.path.join(tmp_d, "swept.noise")
        wf = open(ns_p, "wb")
        try:
            wf.write(
                b'HEADER\nTYPE\n"V" FLOAT DOUBLE PROP( "units" "V" )\n'
                b'"A^2/Hz" FLOAT DOUBLE PROP( "units" "A^2/Hz" )\n'
                b'"resistor" STRUCT( "rn" "A^2/Hz" "total" "A^2/Hz" )\n'
                b'"bsim4" STRUCT( "rd" "A^2/Hz" "rs" "A^2/Hz" "id" "A^2/Hz" "fn" "A^2/Hz" "total" "A^2/Hz" )\n'
                b'SWEEP\n"gs" "V"\nTRACE\n" 1" GROUP 2\n"mn.rg" "resistor"\n"mn.m1" "bsim4"\n'
                b'VALUE\n"gs" 0.0\n" 1"\n( 1e-26 1e-26 )\n( 2e-26 2e-26 3e-24 4e-22 4.03e-22 )\n'
                b'"gs" 0.5\n" 1"\n( 1e-26 1e-26 )\n( 2e-26 2e-26 8e-23 9e-21 9.08e-21 )\nEND\n'
            )
        finally:
            wf.close()
        p_ns = parse_psf_file(ns_p)
        if len(p_ns["values"]["mn.m1:id"]) != 2 or p_ns["field_units"].get("mn.m1:id") != "A^2/Hz":
            raise AssertionError("Swept GROUP STRUCT noise parsing failed!")

        # 4. String value matching a STRUCT type name or TRACE-declared string type must NOT be consumed as type_tag (#19)
        str_p = os.path.join(tmp_d, "str_collision.info")
        wf = open(str_p, "wb")
        try:
            wf.write(
                b'HEADER\nTYPE\n"str_t" STRING *\n'
                b'"bsim4" STRUCT( "gm" FLOAT DOUBLE "vds" FLOAT DOUBLE )\n'
                b'TRACE\n"note" "string"\n"model_kind" "str_t"\n"M1" "bsim4"\n'
                b'VALUE\n'
                b'"note" "str_t"\n'
                b'"model_kind" "bsim4"\n'
                b'"untraced_model" "bsim4"\n'
                b'"M1" "bsim4" ( 1.0e-3 0.5 )\nEND\n'
            )
        finally:
            wf.close()
        p_str = parse_psf_file(str_p)
        if p_str["strings"].get("note") != "str_t":
            raise AssertionError("Declared string trace value 'str_t' was misparsed: %r" % p_str["strings"])
        if p_str["strings"].get("model_kind") != "bsim4":
            raise AssertionError("Declared string value 'bsim4' was misparsed: %r" % p_str["strings"])
        if p_str["strings"].get("untraced_model") != "bsim4":
            raise AssertionError("Untraced string value matching STRUCT type 'bsim4' was misparsed: %r" % p_str["strings"])
        if "M1" not in p_str["instances"] or abs(p_str["instances"]["M1"]["fields"]["gm"] - 1.0e-3) > 1e-12:
            raise AssertionError("STRUCT instance M1 after string collision failed: %r" % p_str["instances"])

        # Mid-sweep inline unit conflict detection (A03)
        u_conf_p = os.path.join(tmp_d, "unit_conflict.dc")
        f_uc = open(u_conf_p, "wb")
        try:
            f_uc.write((
                'HEADER\n"PSFversion" "1.00"\n'
                'TYPE\n"v_t" FLOAT DOUBLE PROP( "units" "V" )\n"i_t" FLOAT DOUBLE PROP( "units" "A" )\n'
                'SWEEP\n"vin" "v_t"\nTRACE\n"VDD" "v_t"\n"VDD:p" "i_t"\nVALUE\n'
                '"vin" 0.0\n"VDD" 1.0\n"VDD:p" -0.001\n'
                '"vin" 0.5\n"VDD" 1.0\n"VDD:p" -0.1 PROP( "units" "mA" )\nEND\n'
            ).encode("utf-8"))
        finally:
            f_uc.close()
        p_uc = parse_psf_file(u_conf_p, reject_nonfinite=True, reject_truncated=True)
        if p_uc.get("unit_conflicts", {}).get("VDD:p") != ["A", "mA"]:
            raise AssertionError("Expected mid-sweep unit_conflicts ['A', 'mA'], got %r" % p_uc.get("unit_conflicts"))

        return {
            "ok": True,
            "self_test": "PASS",
            "truncated_guard_verified": True,
            "leading_gap_tracking_verified": True,
            "swept_struct_noise_verified": True,
            "string_type_tag_collision_verified": True,
            "mid_trace_unit_conflict_verified": True,
            "int_num_types_defined": (int in _INT_TYPES and float in _NUM_TYPES),
        }
    finally:
        shutil.rmtree(tmp_d, ignore_errors=True)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--self-test", "self-test"):
        res = run_self_test()
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP_TEXT)
        return 0

    parser = _SilentOptionParser(add_help_option=False)
    parser.add_option("-h", "--help", action="store_true", dest="help", default=False)
    parser.add_option("--self-test", action="store_true", dest="self_test", default=False)
    parser.add_option("--signal", action="append", dest="signals", default=[])
    parser.add_option("--at-index", type="int", dest="at_index", default=None)
    parser.add_option("--full", action="store_true", dest="full", default=False)
    parser.add_option("--instances", action="store_true", dest="instances", default=False)

    try:
        options, pos_args = parser.parse_args(args)
    except ValueError as err:
        sys.stderr.write("%s\n" % str(err))
        return 2

    if options.self_test:
        res = run_self_test()
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    if options.help:
        print(HELP_TEXT)
        return 0

    path = pos_args[0] if pos_args else None
    signals = list(options.signals)
    if len(pos_args) > 1:
        signals.extend(pos_args[1:])

    if not path or not os.path.isfile(path):
        print(json.dumps({"ok": False, "error": "PSF ASCII file not found: " + str(path)}, indent=2, sort_keys=True))
        return 2

    try:
        parsed = parse_psf_file(path, names=signals if signals else None, reject_nonfinite=True)
        if not parsed["has_value_section"]:
            raise ValueError("No VALUE section found in PSF ASCII file: " + path)
        if not parsed["values"] and not signals and not parsed["instances"]:
            raise ValueError("No numeric VALUE records parsed from: " + path)
        summary = summarize_psf(parsed["values"], full=options.full, at_index=options.at_index)
        payload = {
            "ok": True,
            "path": os.path.realpath(path),
            "signal_count": len(summary),
            "signals": summary,
        }
        if parsed["sweep_name"]:
            payload["sweep_name"] = parsed["sweep_name"]
        if options.instances or parsed["instances"]:
            payload["instance_count"] = len(parsed["instances"])
            if options.instances:
                payload["instances"] = dict(
                    (k, v["fields"]) for k, v in parsed["instances"].items()
                )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "path": path, "error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
