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

function readFeishuJson(filename: string): FeishuResponse {
  const filePath = path.join(process.cwd(), "src/data/feishu", filename);
  const raw = fs.readFileSync(filePath, "utf-8");
  const parsed: unknown = JSON.parse(raw);

  if (!parsed || typeof parsed !== "object") {
    throw new Error(`飞书数据顶层格式无效: ${filename}`);
  }
  const response = parsed as Partial<FeishuResponse>;
  const data = response.data;
  if (
    response.ok !== true ||
    !data ||
    !Array.isArray(data.fields) ||
    !data.fields.every((field) => typeof field === "string") ||
    !Array.isArray(data.data) ||
    !Array.isArray(data.record_id_list) ||
    data.data.length !== data.record_id_list.length ||
    !data.data.every(
      (row) => Array.isArray(row) && row.length === data.fields.length
    )
  ) {
    throw new Error(`飞书数据契约无效: ${filename}`);
  }
  return response as FeishuResponse;
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

function requiredText(value: unknown, field: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`飞书字段必须是非空文本: ${field}`);
  }
  return value;
}

function finiteNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`飞书字段必须是有限数字: ${field}`);
  }
  return value;
}

// ============ 数据读取 ============

export function getFinancialData(): MonthlyFinance[] {
  const resp = readFeishuJson("finance.json");
  const rows = parseRows(resp);
  return rows
    .map((r) => ({
      month: requiredText(r["月份"], "finance.月份"),
      debt: finiteNumber(r["负债"], "finance.负债"),
      income: finiteNumber(r["收入"], "finance.收入"),
      expense: finiteNumber(r["支出"], "finance.支出"),
      netWorth: finiteNumber(r["净资产"], "finance.净资产"),
    }))
    .sort((left, right) => left.month.localeCompare(right.month));
}

export function getBusinessLines(): BusinessLine[] {
  const resp = readFeishuJson("business.json");
  const rows = parseRows(resp);
  return rows.map((r) => {
    const statusArr = r["状态"];
    const status = Array.isArray(statusArr) ? statusArr[0] : String(statusArr ?? "规划中");
    const tagsRaw = typeof r["标签"] === "string" ? r["标签"] : "";
    return {
      id: String(r._id),
      name: requiredText(r["名称"], "business.名称"),
      description: typeof r["描述"] === "string" ? r["描述"] : "",
      status,
      startDate: requiredText(r["启动日期"], "business.启动日期").split(" ")[0],
      revenue: finiteNumber(r["累计收入"], "business.累计收入"),
      tags: tagsRaw ? tagsRaw.split(",").map((t) => t.trim()) : [],
    };
  });
}

export function getLogEntries(): LogEntry[] {
  const resp = readFeishuJson("logs.json");
  const rows = parseRows(resp);
  return rows.map((r) => {
    const date = requiredText(r["日期"], "logs.日期").split(" ")[0];
    const moodArr = r["心情"];
    const mood = Array.isArray(moodArr) ? moodArr[0] : String(moodArr ?? "平稳");
    const tagsRaw = typeof r["标签"] === "string" ? r["标签"] : "";
    return {
      slug: date,
      date,
      title: requiredText(r["标题"], "logs.标题"),
      summary: typeof r["摘要"] === "string" ? r["摘要"] : "",
      mood,
      tags: tagsRaw ? tagsRaw.split(",").map((t) => t.trim()) : [],
      content: requiredText(r["正文"], "logs.正文"),
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
