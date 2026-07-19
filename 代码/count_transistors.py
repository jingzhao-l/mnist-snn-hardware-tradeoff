#!/usr/bin/env python3
"""
count_transistors.py — 从 Cadence CDL netlist 自动统计晶体管数量
===========================================================
不需要手工一个一个数。脚本会：
  1. 解析 .cdl 文件里的 .SUBCKT 层次结构
  2. 统计每个子电路直接的 MOSFET（M 开头器件）
  3. 递归展开子电路实例，得到顶层总晶体管数

用法：
    python count_transistors.py
    python count_transistors.py /path/to/IF10.cdl /path/to/MAC9.cdl
"""

import os
import re
import sys
from collections import Counter


def join_continuation_lines(raw_lines):
    """把 SPICE 中以 '+' 开头的续行合并到上一行。"""
    joined = []
    for line in raw_lines:
        line = line.rstrip('\n')
        if line.startswith('+'):
            if joined:
                joined[-1] = joined[-1].rstrip() + ' ' + line[1:].strip()
            else:
                joined.append(line)
        else:
            joined.append(line)
    return joined


def parse_cdl(path):
    """解析单个 CDL 文件。

    Returns:
        subcircuits: dict, key=子电路名, value={direct_m, instances}
        top_cell: str, 顶层单元名（从 * Top Cell Name: 提取）
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = join_continuation_lines(f.readlines())

    subcircuits = {}
    current = None
    top_cell = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('*'):
            # 提取顶层单元名
            m = re.search(r'Top Cell Name:\s*(\S+)', stripped)
            if m:
                top_cell = m.group(1)
            continue

        upper = stripped.upper()

        if upper.startswith('.SUBCKT'):
            parts = stripped.split()
            if len(parts) < 2:
                continue
            name = parts[1]
            current = name
            subcircuits[current] = {'direct_m': 0, 'instances': []}
        elif upper.startswith('.ENDS'):
            current = None
        elif current is not None:
            if upper.startswith('M'):
                subcircuits[current]['direct_m'] += 1
            elif upper.startswith('X'):
                tokens = stripped.split()
                subname = None
                if '/' in tokens:
                    idx = tokens.index('/')
                    if idx + 1 < len(tokens):
                        subname = tokens[idx + 1]
                else:
                    # 没有 '/' 时默认最后一个 token 为子电路名
                    subname = tokens[-1]
                if subname:
                    subcircuits[current]['instances'].append(subname)

    return subcircuits, top_cell


def count_transistors(subcircuits, top_name, _memo=None):
    """递归计算指定顶层单元的总晶体管数（含所有子电路实例）。"""
    if _memo is None:
        _memo = {}
    if top_name in _memo:
        return _memo[top_name]

    if top_name not in subcircuits:
        raise ValueError(f"未找到子电路: {top_name}")

    sub = subcircuits[top_name]
    total = sub['direct_m']
    inst_counter = Counter(sub['instances'])

    for subname, count in inst_counter.items():
        total += count * count_transistors(subcircuits, subname, _memo)

    _memo[top_name] = total
    return total


def breakdown(subcircuits, top_name):
    """生成顶层单元的晶体管数量分解表。"""
    totals = {}
    counts = Counter(subcircuits[top_name]['instances'])
    rows = []

    # 顶层自己直接画出的晶体管
    rows.append((top_name, '直接 MOSFET', subcircuits[top_name]['direct_m']))

    # 各子电路实例的贡献
    for subname in sorted(counts.keys()):
        n_inst = counts[subname]
        per_inst = count_transistors(subcircuits, subname)
        rows.append((subname, f'{n_inst} 个实例 × {per_inst}', n_inst * per_inst))

    rows.append((top_name, '总计', count_transistors(subcircuits, top_name)))
    return rows


def run_tests():
    """用一段最小 CDL 做单元测试。"""
    sample = """
* Top Cell Name: TOP
.SUBCKT INV VDD! gnd! input output
MPM0 output input VDD! VDD! p18 W=1u L=180n m=1
MNM0 output input gnd! gnd! n18 W=500n L=180n m=1
.ENDS

.SUBCKT AND2 A B VDD! gnd! output
XI0 VDD! gnd! net1 output / INV
XI1 VDD! gnd! net1 output / INV
.ENDS

.SUBCKT TOP A B VDD! gnd! out
XI0 A B VDD! gnd! net1 / AND2
XI1 VDD! gnd! net1 out / INV
.ENDS
"""
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.cdl', delete=False) as f:
        f.write(sample)
        tmp = f.name

    try:
        subs, top = parse_cdl(tmp)
        assert top == 'TOP'
        assert count_transistors(subs, 'INV') == 2
        assert count_transistors(subs, 'AND2') == 4
        assert count_transistors(subs, 'TOP') == 6
        print('[测试通过] 最小 CDL 解析与计数正确')
    finally:
        os.unlink(tmp)


def main(paths):
    if not paths:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(base_dir, '..', '报告', 'IF_final.cdl'),
            os.path.join(base_dir, '..', '报告', 'MAC_final.cdl'),
        ]

    for path in paths:
        print('\n' + '=' * 60)
        print(f'文件: {path}')
        print('=' * 60)

        if not os.path.exists(path):
            print(f'[跳过] 文件不存在: {path}')
            continue

        subcircuits, top_cell = parse_cdl(path)
        if top_cell is None:
            print('[错误] 无法从文件头提取 Top Cell Name')
            continue

        print(f'顶层单元: {top_cell}')
        rows = breakdown(subcircuits, top_cell)

        name_width = max(len(r[0]) for r in rows)
        detail_width = max(len(r[1]) for r in rows)
        for name, detail, count in rows:
            print(f'  {name:<{name_width}}  {detail:<{detail_width}}  {count:>6} 晶体管')

        total = count_transistors(subcircuits, top_cell)
        print(f'\n  ==> {top_cell} 总晶体管数: {total}')


if __name__ == '__main__':
    run_tests()
    main(sys.argv[1:])
