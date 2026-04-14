import Link from "next/link";
import FinanceCard from "@/components/FinanceCard";
import {
  formatMoney,
  getCurrentNetWorth,
  getDaysSinceStart,
  getTotalIncome,
  TARGET,
  getBusinessLines,
  getLogEntries,
  statusToEn,
} from "@/data/finance";

export default function Home() {
  const netWorth = getCurrentNetWorth();
  const daysSince = getDaysSinceStart();
  const totalIncome = getTotalIncome();
  const progress = ((totalIncome / TARGET) * 100).toFixed(1);
  const logEntries = getLogEntries();
  const businessLines = getBusinessLines();
  const latestLog = logEntries[logEntries.length - 1];

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      {/* Hero */}
      <section className="py-12 sm:py-28">
        <div className="animate-fade-in flex items-center gap-2 sm:gap-3 flex-wrap">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#818cf8]/30 bg-[#818cf8]/10 px-3 sm:px-4 py-1 sm:py-1.5 text-xs sm:text-sm text-[#818cf8] font-semibold tracking-wide">
            OPC 一人公司
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#34d399]/30 bg-[#34d399]/10 px-3 sm:px-4 py-1 sm:py-1.5 text-xs sm:text-sm text-[#34d399] font-semibold">
            × AI
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/5 px-2.5 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm text-primary">
            <span className="inline-block h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-primary pulse-red" />
            Day {daysSince}
          </span>
        </div>

        <h1 className="mt-6 sm:mt-8 text-3xl sm:text-6xl font-bold leading-tight animate-fade-in">
          从<span className="text-negative">负债360万</span>
          <br />
          到<span className="text-accent">年赚千万</span>
        </h1>

        <p className="mt-4 sm:mt-6 max-w-2xl text-base sm:text-lg text-text-secondary animate-fade-in-delay">
          负债360万，不招一个员工。
          <strong className="text-[#818cf8]">一个人</strong> +
          <strong className="text-[#34d399]"> AI Agent</strong> =
          一家完整的公司。
          <br className="hidden sm:block" />
          这是一个<strong className="text-text">OPC一人公司</strong>的全过程真实记录。
        </p>

        <div className="mt-8 sm:mt-10 flex gap-3 sm:gap-4 animate-fade-in-delay">
          <Link
            href="/log"
            className="rounded-lg bg-[#818cf8] px-5 sm:px-6 py-2.5 sm:py-3 text-sm sm:text-base font-medium text-white transition-colors hover:bg-[#6366f1]"
          >
            查看执行日志
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-[#1e1e2e] px-5 sm:px-6 py-2.5 sm:py-3 text-sm sm:text-base font-medium text-text-secondary transition-colors hover:bg-[#0d0d14] hover:text-text"
          >
            财务看板
          </Link>
        </div>
      </section>

      {/* OPC 公式 */}
      <section className="pb-10 sm:pb-16">
        <div className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-5 sm:p-8">
          <div className="flex items-center justify-around sm:grid sm:grid-cols-3 sm:gap-6 text-center">
            <div>
              <div className="text-3xl sm:text-4xl mb-1 sm:mb-2">👤</div>
              <div className="text-lg sm:text-2xl font-bold text-[#818cf8]">1 个人</div>
              <div className="text-xs sm:text-sm text-text-muted mt-1">决策者</div>
            </div>
            <div>
              <div className="text-xl sm:text-3xl text-text-muted">+</div>
              <div className="text-3xl sm:text-4xl mb-1 sm:mb-2">🤖</div>
              <div className="text-lg sm:text-2xl font-bold text-[#34d399]">AI Agent</div>
              <div className="text-xs sm:text-sm text-text-muted mt-1">全栈团队</div>
            </div>
            <div>
              <div className="text-xl sm:text-3xl text-text-muted">=</div>
              <div className="text-3xl sm:text-4xl mb-1 sm:mb-2">🎯</div>
              <div className="text-lg sm:text-2xl font-bold text-accent">年赚千万</div>
              <div className="text-xs sm:text-sm text-text-muted mt-1">极限在哪？</div>
            </div>
          </div>
        </div>
      </section>

      {/* 实时数据 */}
      <section className="pb-10 sm:pb-16">
        <h2 className="mb-6 text-sm font-medium uppercase tracking-wider text-text-muted">
          实时数据
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <FinanceCard
            label="当前净资产"
            value={formatMoney(netWorth)}
            subtext={`起点: ${formatMoney(-3600000)}`}
            trend="down"
            highlight
          />
          <FinanceCard
            label="累计收入"
            value={formatMoney(totalIncome)}
            subtext={`目标: ${formatMoney(TARGET)}`}
            trend="neutral"
          />
          <FinanceCard
            label="已经过去"
            value={`${daysSince} 天`}
            subtext="0 员工 · N 个 AI Agent"
            trend="neutral"
          />
          <FinanceCard
            label="目标进度"
            value={`${progress}%`}
            subtext="OPC模式验证中"
            trend="neutral"
          />
        </div>
      </section>

      {/* 进度条 */}
      <section className="pb-10 sm:pb-16">
        <div className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-text-muted">OPC一人公司 → 年赚千万</span>
            <span className="text-sm font-mono text-[#818cf8]">{progress}%</span>
          </div>
          <div className="h-3 w-full rounded-full bg-[#1e1e2e] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#818cf8] via-[#34d399] to-[#f59e0b] transition-all duration-1000"
              style={{ width: `${Math.max(parseFloat(progress), 0.5)}%` }}
            />
          </div>
          <div className="mt-3 flex justify-between text-xs text-text-muted">
            <span>-360万</span>
            <span>0</span>
            <span>+1000万/年</span>
          </div>
        </div>
      </section>

      {/* 最新动态 */}
      <section className="pb-10 sm:pb-16">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">最新动态</h2>
          <Link href="/log" className="text-sm text-[#818cf8] hover:text-[#6366f1]">查看全部 →</Link>
        </div>

        {latestLog && (
          <Link
            href={`/log/${latestLog.slug}`}
            className="block rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6 transition-colors hover:bg-[#111118]"
          >
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs text-text-muted font-mono">{latestLog.date}</span>
              <span className="inline-flex items-center rounded-full bg-[#818cf8]/10 px-2 py-0.5 text-xs text-[#818cf8]">{latestLog.mood}</span>
            </div>
            <h3 className="text-xl font-semibold">{latestLog.title}</h3>
            <p className="mt-2 text-text-secondary">{latestLog.summary}</p>
            <div className="mt-4 flex gap-2">
              {latestLog.tags.map((tag) => (
                <span key={tag} className="rounded-md bg-[#08080c] px-2 py-1 text-xs text-text-muted">#{tag}</span>
              ))}
            </div>
          </Link>
        )}
      </section>

      {/* 业务线 */}
      <section className="pb-20">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-sm font-medium uppercase tracking-wider text-text-muted">OPC 业务线</h2>
          <Link href="/business" className="text-sm text-[#818cf8] hover:text-[#6366f1]">详情 →</Link>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {businessLines.map((biz) => {
            const st = statusToEn(biz.status);
            return (
              <div key={biz.id} className="rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold">{biz.name}</h3>
                  <span className={`rounded-full px-2 py-0.5 text-xs ${
                    st === "launched" || st === "growing"
                      ? "bg-positive/10 text-positive"
                      : st === "building"
                        ? "bg-[#818cf8]/10 text-[#818cf8]"
                        : "bg-[#0d0d14] text-text-muted"
                  }`}>
                    {biz.status}
                  </span>
                </div>
                <p className="text-sm text-text-secondary">{biz.description}</p>
                <p className="mt-3 text-sm font-mono text-text-muted">收入: {formatMoney(biz.revenue)}</p>
              </div>
            );
          })}
          <div className="rounded-xl border border-dashed border-[#1e1e2e] bg-[#0d0d14]/50 p-6 flex items-center justify-center">
            <p className="text-text-muted text-sm">更多OPC业务线待开拓...</p>
          </div>
        </div>
      </section>
    </div>
  );
}
