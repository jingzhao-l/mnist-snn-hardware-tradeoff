"""
generate_full_table.py — 生成完整数据表格 Markdown
"""
import csv
import os


def csv_to_md(csv_path, title):
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(filter(lambda line: not line.startswith('#'), f))
        for r in reader:
            rows.append(r)

    md = [f"## {title}\n"]
    md.append("| T | Vth | 准确率(%) | 整体稀疏率(%) | P_if(µW) | P_mac(µW) | P_SNN(mW·cycle) | P_ANN(mW·cycle) | 节能(%) | SNN/ANN(%) |")
    md.append("|---|---|---|---|---|---|---|---|---|---|")

    for r in rows:
        p_snn = float(r['P_SNN_uW']) / 1000.0
        p_ann = float(r['P_ANN_uW']) / 1000.0
        ratio = p_snn / p_ann * 100.0
        md.append(
            f"| {r['T']} | {r['Vth']} | {r['Accuracy(%)']} | {r['Overall_Sparsity(%)']} | "
            f"{float(r['P_if_single_uW']):.3f} | {float(r['P_mac_single_uW']):.3f} | "
            f"{p_snn:.3f} | {p_ann:.3f} | {r['power_saving_percent']} | {ratio:.3f} |"
        )

    md.append("")
    return "\n".join(md)


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_based_csv = os.path.join(base_dir, "snn_tradeoff_data_based.csv")
    max_norm_csv = os.path.join(base_dir, "snn_tradeoff_max_norm.csv")
    output_md = os.path.join(base_dir, "full_results_table.md")

    content = "# SNN-ANN Trade-off 完整数据表\n\n"
    content += "> 功耗模型：P_if = 9.611 µW（已按 11 周期 / 3 事件折算），P_mac = 4.870 µW（A/B 输入翻转），ANN 并行度 = 1。\n\n"
    content += csv_to_md(data_based_csv, "data_based 归一化")
    content += "\n"
    content += csv_to_md(max_norm_csv, "max_norm 归一化")

    with open(output_md, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[完成] 完整数据表已保存到 {output_md}")
