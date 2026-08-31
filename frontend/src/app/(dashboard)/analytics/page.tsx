"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { BarChart3, TrendingUp, Building2, Package } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<any>(null);
  const [modules, setModules] = useState<any[]>([]);
  const [subscriptions, setSubscriptions] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/admin/security/analytics/overview"),
      api.get("/admin/security/analytics/modules"),
      api.get("/admin/security/analytics/subscriptions"),
    ]).then(([ov, md, sub]) => {
      if (ov.data.success) setOverview(ov.data);
      if (md.data.success) setModules(md.data.modules);
      if (sub.data.success) setSubscriptions(sub.data);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" /></div>;

  const moduleData = modules.slice(0, 8).map((m) => ({ name: m.module_code, adoption: m.adoption_pct }));
  const subData = subscriptions ? Object.entries(subscriptions.statuses).map(([k, v]) => ({ name: k, value: v as number })) : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Analytics</h1>

      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm">Total Revenue</p>
            <p className="text-2xl font-bold text-white mt-1">${overview.revenue.total.toLocaleString()}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm">Revenue (30d)</p>
            <p className="text-2xl font-bold text-green-400 mt-1">${overview.revenue.last_30d.toLocaleString()}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm">Active Companies</p>
            <p className="text-2xl font-bold text-white mt-1">{overview.companies.active}</p>
          </div>
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm">Module Grants</p>
            <p className="text-2xl font-bold text-white mt-1">{overview.modules.company_module_grants}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
          <h3 className="text-white font-semibold mb-4">Module Adoption (%)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={moduleData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <YAxis dataKey="name" type="category" width={100} tick={{ fill: "#94a3b8", fontSize: 12 }} />
              <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "12px", color: "#fff" }} />
              <Bar dataKey="adoption" fill="#3b82f6" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
          <h3 className="text-white font-semibold mb-4">Subscription Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={subData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={4} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                {subData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "12px", color: "#fff" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-6">
        <h3 className="text-white font-semibold mb-4">Module Adoption Details</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700/50">
                <th className="text-right py-3 px-4">Module</th>
                <th className="text-right py-3 px-4">Enabled</th>
                <th className="text-right py-3 px-4">Total Companies</th>
                <th className="text-right py-3 px-4">Adoption</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((m) => (
                <tr key={m.module_code} className="border-b border-slate-700/30 hover:bg-slate-700/20">
                  <td className="py-3 px-4 text-white font-medium">{m.module_name}</td>
                  <td className="py-3 px-4 text-slate-300">{m.enabled_count}</td>
                  <td className="py-3 px-4 text-slate-400">{m.total_companies}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${m.adoption_pct}%` }} />
                      </div>
                      <span className="text-slate-300 text-xs">{m.adoption_pct}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
