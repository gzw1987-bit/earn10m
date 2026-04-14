import { getBusinessLines, formatMoney, statusToEn } from "@/data/finance";

const statusColors: Record<string, string> = {
  "规划中": "bg-bg text-text-muted border-border",
  "建设中": "bg-[#818cf8]/10 text-[#818cf8] border-[#818cf8]/20",
  "已上线": "bg-positive/10 text-positive border-positive/20",
  "增长中": "bg-positive/10 text-positive border-positive/20",
  "暂停": "bg-bg text-text-muted border-border",
};

export default function BusinessPage() {
  const businessLines = getBusinessLines();
  const totalRevenue = businessLines.reduce((sum, b) => sum + b.revenue, 0);
  const activeCount = businessLines.filter((b) => {
    const st = statusToEn(b.status);
    return st !== "paused" && st !== "planning";
  }).length;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-12">
      <div className="flex items-center gap-3 mb-2">
        <span className="inline-flex items-center rounded-full border border-[#818cf8]/30 bg-[#818cf8]/10 px-3 py-1 text-xs text-[#818cf8] font-semibold tracking-wide">OPC</span>
        <h1 className="text-3xl font-bold">业务线</h1>
      </div>
      <p className="mt-2 text-text-secondary">
        一人公司的所有业务 — 1个人 + AI Agent 运营
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <p className="text-sm text-text-muted">业务线总数</p>
          <p className="mt-2 text-3xl font-bold">{businessLines.length}</p>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <p className="text-sm text-text-muted">活跃业务</p>
          <p className="mt-2 text-3xl font-bold text-[#818cf8]">{activeCount}</p>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-6">
          <p className="text-sm text-text-muted">总收入</p>
          <p className="mt-2 text-3xl font-bold font-mono">{formatMoney(totalRevenue)}</p>
        </div>
      </div>

      <div className="mt-12 space-y-6">
        {businessLines.map((biz) => (
          <div key={biz.id} className="rounded-xl border border-border bg-bg-card p-6">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-semibold">{biz.name}</h2>
                  <span className={`rounded-full border px-3 py-0.5 text-xs ${statusColors[biz.status] ?? "bg-bg text-text-muted border-border"}`}>
                    {biz.status}
                  </span>
                </div>
                <p className="mt-2 text-text-secondary">{biz.description}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-text-muted">累计收入</p>
                <p className="text-xl font-bold font-mono">{formatMoney(biz.revenue)}</p>
              </div>
            </div>
            <div className="mt-4 flex items-center gap-4 text-sm text-text-muted">
              <span>启动: {biz.startDate}</span>
              <span>|</span>
              <div className="flex gap-2">
                {biz.tags.map((tag) => (
                  <span key={tag} className="rounded-md bg-bg px-2 py-0.5 text-xs">#{tag}</span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* OPC五大变现模式 */}
      <div className="mt-12 rounded-xl border border-[#1e1e2e] bg-[#0d0d14] p-6">
        <h2 className="text-xl font-semibold mb-2">OPC 五大变现模式</h2>
        <p className="text-sm text-text-muted mb-4">基于OPC一人公司模式，AI赋能的五大方向</p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { icon: "🛠", title: "AI工具类", desc: "轻量SaaS、效率插件", detail: "一次开发，持续收费" },
            { icon: "📝", title: "AI内容类", desc: "短视频素材、知识付费", detail: "低边际成本，易规模化" },
            { icon: "🎯", title: "AI服务类", desc: "1对N咨询、定制方案", detail: "高单价，AI放大交付能力" },
            { icon: "🎨", title: "AI文创类", desc: "数字设计+实体交付", detail: "差异化强" },
            { icon: "🛒", title: "AI优化交易", desc: "智能选品、跨境电商", detail: "信息差+效率差" },
            { icon: "🚀", title: "更多方向", desc: "随实践持续探索", detail: "OPC的边界在哪？" },
          ].map((item) => (
            <div key={item.title} className="rounded-lg border border-[#1e1e2e] bg-[#08080c] p-4">
              <div className="text-2xl mb-2">{item.icon}</div>
              <h3 className="font-semibold text-sm">{item.title}</h3>
              <p className="text-xs text-text-secondary mt-1">{item.desc}</p>
              <p className="text-xs text-text-muted mt-1">{item.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
