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

export default function DashboardPage() {
  const financialData = getFinancialData();
  const netWorth = getCurrentNetWorth();
  const debt = getCurrentDebt();
  const totalIncome = getTotalIncome();
  const totalExpense = financialData.reduce((sum, m) => sum + m.expense, 0);
  const daysSince = getDaysSinceStart();
  const progress = ((totalIncome / TARGET) * 100).toFixed(1);

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-12">
      <h1 className="text-3xl font-bold">财务看板</h1>
      <p className="mt-2 text-text-secondary">
        完全透明的财务数据，每月更新
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <FinanceCard
          label="当前负债"
          value={formatMoney(debt)}
          subtext={`起始: ${formatMoney(START_DEBT)}`}
          trend="down"
          highlight
        />
        <FinanceCard
          label="当前净资产"
          value={formatMoney(netWorth)}
          trend={netWorth > START_DEBT ? "up" : "down"}
        />
        <FinanceCard
          label="累计收入"
          value={formatMoney(totalIncome)}
          subtext={`日均: ${formatMoney(daysSince > 0 ? Math.round(totalIncome / daysSince) : 0)}`}
          trend="up"
        />
        <FinanceCard
          label="累计支出"
          value={formatMoney(totalExpense)}
          trend="neutral"
        />
      </div>

      <div className="mt-12">
        <h2 className="text-xl font-semibold mb-4">目标进度</h2>
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <div>
              <p className="text-sm text-text-muted">年赚千万目标</p>
              <p className="mt-1 text-2xl font-bold font-mono">{progress}%</p>
              <div className="mt-2 h-2 w-full rounded-full bg-border overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(parseFloat(progress), 0.5)}%` }}
                />
              </div>
            </div>
            <div>
              <p className="text-sm text-text-muted">还需要赚</p>
              <p className="mt-1 text-2xl font-bold font-mono text-accent">
                {formatMoney(TARGET - totalIncome)}
              </p>
            </div>
            <div>
              <p className="text-sm text-text-muted">已过天数</p>
              <p className="mt-1 text-2xl font-bold font-mono">{daysSince} 天</p>
            </div>
          </div>
        </div>
      </div>

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
                <tr
                  key={row.month}
                  className={`border-t border-border ${i % 2 === 0 ? "" : "bg-bg-card/50"}`}
                >
                  <td className="px-4 py-3 font-mono">{row.month}</td>
                  <td className="px-4 py-3 text-right text-positive font-mono">
                    {formatMoney(row.income)}
                  </td>
                  <td className="px-4 py-3 text-right text-text-secondary font-mono">
                    {formatMoney(row.expense)}
                  </td>
                  <td className="px-4 py-3 text-right text-negative font-mono">
                    {formatMoney(row.debt)}
                  </td>
                  <td className="px-4 py-3 text-right font-bold font-mono">
                    {formatMoney(row.netWorth)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-12 rounded-xl border border-border bg-bg-card p-6">
        <h3 className="font-semibold mb-2">数据说明</h3>
        <ul className="text-sm text-text-secondary space-y-1">
          <li>- 所有财务数据每月更新，力求真实准确</li>
          <li>- 数据来源：飞书多维表格，自动同步到网站</li>
          <li>- 收入包含所有业务线的营收（税前）</li>
          <li>- 净资产 = 累计收入 - 累计支出 + 初始负债</li>
        </ul>
      </div>
    </div>
  );
}
