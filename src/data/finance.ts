import fs from "fs";
import path from "path";

// ============ 类型定义 ============

export interface MonthlyFinance {
  month: string;
  debt: number;
  income: number;
  expense: number;
  netWorth: number;
}

export interface BusinessLine {
  id: string;
  name: string;
  description: string;
  status: string;
  startDate: string;
  revenue: number;
  tags: string[];
}

export interface LogEntry {
  slug: string;
  date: string;
  title: string;
  summary: string;
  mood: string;
  tags: string[];
  content: string;
}

// ============ 常量 ============

export const TARGET = 10_000_000;
export const START_DEBT = -3_600_000;
export const START_DATE = "2026-04-13";

// ============ 飞书数据解析 ============

interface FeishuResponse {
  ok: boolean;
  data: {
    fields: string[];
    data: unknown[][];
    record_id_list: string[];
  };
}

function readFeishuJson(filename: string): FeishuResponse | null {
  try {
    const filePath = path.join(process.cwd(), "src/data/feishu", filename);
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function parseRows(
  response: FeishuResponse
): Record<string, unknown>[] {
  const { fields, data, record_id_list } = response.data;
  return data.map((row, i) => {
    const obj: Record<string, unknown> = { _id: record_id_list[i] };
    fields.forEach((fieldName, j) => {
      obj[fieldName] = row[j];
    });
    return obj;
  });
}

// ============ 数据读取 ============

export function getFinancialData(): MonthlyFinance[] {
  const resp = readFeishuJson("finance.json");
  if (!resp?.ok) {
    return [{ month: "2026-04", debt: -3600000, income: 0, expense: 0, netWorth: -3600000 }];
  }
  const rows = parseRows(resp);
  return rows.map((r) => ({
    month: String(r["月份"] ?? ""),
    debt: Number(r["负债"] ?? 0),
    income: Number(r["收入"] ?? 0),
    expense: Number(r["支出"] ?? 0),
    netWorth: Number(r["净资产"] ?? 0),
  }));
}

export function getBusinessLines(): BusinessLine[] {
  const resp = readFeishuJson("business.json");
  if (!resp?.ok) {
    return [];
  }
  const rows = parseRows(resp);
  return rows.map((r) => {
    const statusArr = r["状态"];
    const status = Array.isArray(statusArr) ? statusArr[0] : String(statusArr ?? "规划中");
    const tagsRaw = String(r["标签"] ?? "");
    return {
      id: String(r._id),
      name: String(r["名称"] ?? ""),
      description: String(r["描述"] ?? ""),
      status,
      startDate: String(r["启动日期"] ?? "").split(" ")[0],
      revenue: Number(r["累计收入"] ?? 0),
      tags: tagsRaw ? tagsRaw.split(",").map((t) => t.trim()) : [],
    };
  });
}

export function getLogEntries(): LogEntry[] {
  const resp = readFeishuJson("logs.json");
  if (!resp?.ok) {
    return [];
  }
  const rows = parseRows(resp);
  return rows.map((r) => {
    const date = String(r["日期"] ?? "").split(" ")[0];
    const moodArr = r["心情"];
    const mood = Array.isArray(moodArr) ? moodArr[0] : String(moodArr ?? "平稳");
    const tagsRaw = String(r["标签"] ?? "");
    return {
      slug: date,
      date,
      title: String(r["标题"] ?? ""),
      summary: String(r["摘要"] ?? ""),
      mood,
      tags: tagsRaw ? tagsRaw.split(",").map((t) => t.trim()) : [],
      content: String(r["正文"] ?? ""),
    };
  });
}

// ============ 计算函数 ============

export function getTotalIncome(): number {
  return getFinancialData().reduce((sum, m) => sum + m.income, 0);
}

export function getCurrentDebt(): number {
  const data = getFinancialData();
  const latest = data[data.length - 1];
  return latest?.debt ?? START_DEBT;
}

export function getCurrentNetWorth(): number {
  const data = getFinancialData();
  const latest = data[data.length - 1];
  return latest?.netWorth ?? START_DEBT;
}

export function getDaysSinceStart(): number {
  const start = new Date(START_DATE);
  const now = new Date();
  return Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
}

export function formatMoney(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";
  if (abs >= 10000) {
    return `${sign}${(abs / 10000).toFixed(1)}万`;
  }
  return `${sign}${abs.toLocaleString()}`;
}

// 心情映射
const moodMap: Record<string, string> = {
  "极佳": "great",
  "不错": "good",
  "平稳": "neutral",
  "有点难": "tough",
  "很艰难": "terrible",
};

export function moodToEn(mood: string): string {
  return moodMap[mood] ?? "neutral";
}

// 状态映射
const statusMap: Record<string, string> = {
  "规划中": "planning",
  "建设中": "building",
  "已上线": "launched",
  "增长中": "growing",
  "暂停": "paused",
};

export function statusToEn(status: string): string {
  return statusMap[status] ?? "planning";
}
