import FinanceCard from "@/components/FinanceCard";
import {
  getFinancialData,
  formatMoney,
  getCurrentDebt,
  getCurrentNetWorth,
  getTotalIncome,
  getDaysSinceStart,
  TARGET,
  START_DEBT,
} from "@/data/finance";

export default function OPCDashboardPage() {
  const financialData = getFinancialData();
  const netWorth = getCurrentNetWorth();
  const debt = getCurrentDebt();
  const totalIncome = getTotalIncome();
  const totalExpense = financialData.reduce((sum, m) => sum + m.expense, 0);
  const daysSince = getDaysSinceStart();
  const progress = ((totalIncome / TARGET) * 100).toFixed(1);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-12">
      <div className="flex items-center gap-3 mb-2">
        <span className="inline-flex items-center rounded-full border border-[#818cf8]/30 bg-[#818cf8]/10 px-3 py-1 text-xs text-[#818cf8] font-semibold tracking-wide">OPC</span>
        <h1 className="text-3xl font-bold">财务看板</h1>
      </div>
      <p className="mt-2 text-text-secondary">
        一人公司，完全透明的财务数据 — 0员工，全靠AI
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <FinanceCard label="当前负债" value={formatMoney(debt)} subtext={`起始: ${formatMoney(START_DEBT)}`} trend="down" highlight />
        <FinanceCard label="当前净资产" value={formatMoney(netWorth)} trend={netWorth > START_DEBT ? "up" : "down"} />
        <FinanceCard label="累计收入" value={formatMoney(totalIncome)} subtext={`日均: ${formatMoney(daysSince > 0 ? Math.round(totalIncome / daysSince) : 0)}`} trend="up" />
        <FinanceCard label="累计支出" value={formatMoney(totalExpense)} subtext="含AI工具成本" trend="neutral" />
      </div>

      {/* OPC效率指标 */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold mb-4">OPC 效率指标</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
            <p className="text-sm text-text-muted">员工人数</p>
            <p className="mt-2 text-3xl font-bold text-[#818cf8]">0 人</p>
            <p className="text-xs text-text-muted mt-1">纯OPC模式</p>
          </div>
          <div className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
            <p className="text-sm text-text-muted">AI Agent数量</p>
            <p className="mt-2 text-3xl font-bold text-[#34d399]">搭建中</p>
            <p className="text-xs text-text-muted mt-1">持续增加</p>
          </div>
          <div className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
            <p className="text-sm text-text-muted">人力杠杆率</p>
            <p className="mt-2 text-3xl font-bold text-accent">1:72</p>
            <p className="text-xs text-text-muted mt-1">1元AI ≈ 72元人力</p>
          </div>
        </div>
      </div>

      {/* 目标进度 */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold mb-4">目标进度</h2>
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <div>
              <p className="text-sm text-text-muted">年赚千万目标</p>
              <p className="mt-1 text-2xl font-bold font-mono">{progress}%</p>
              <div className="mt-2 h-2 w-full rounded-full bg-border overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-[#818cf8] to-[#34d399]" style={{ width: `${Math.max(parseFloat(progress), 0.5)}%` }} />
              </div>
            </div>
            <div>
              <p className="text-sm text-text-muted">还需要赚</p>
              <p className="mt-1 text-2xl font-bold font-mono text-accent">{formatMoney(TARGET - totalIncome)}</p>
            </div>
            <div>
              <p className="text-sm text-text-muted">已过天数</p>
              <p className="mt-1 text-2xl font-bold font-mono">{daysSince} 天</p>
            </div>
          </div>
        </div>
      </div>

      {/* 月度明细 */}
      <div className="mt-12">
        <h2 className="text-xl font-semibold mb-4">月度明细</h2>
        <div className="rounded-xl border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bg-card text-text-muted">
                <th className="px-4 py-3 text-left font-medium">月份</th>
                <th className="px-4 py-3 text-right font-medium">收入</th>
                <th className="px-4 py-3 text-right font-medium">支出</th>
                <th className="px-4 py-3 text-right font-medium">负债</th>
                <th className="px-4 py-3 text-right font-medium">净资产</th>
              </tr>
            </thead>
            <tbody>
              {financialData.map((row, i) => (
                <tr key={row.month} className={`border-t border-border ${i % 2 === 0 ? "" : "bg-bg-card/50"}`}>
                  <td className="px-4 py-3 font-mono">{row.month}</td>
                  <td className="px-4 py-3 text-right text-positive font-mono">{formatMoney(row.income)}</td>
                  <td className="px-4 py-3 text-right text-text-secondary font-mono">{formatMoney(row.expense)}</td>
                  <td className="px-4 py-3 text-right text-negative font-mono">{formatMoney(row.debt)}</td>
                  <td className="px-4 py-3 text-right font-bold font-mono">{formatMoney(row.netWorth)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
