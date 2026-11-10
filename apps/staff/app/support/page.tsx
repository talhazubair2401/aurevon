"use client";

import Link from "next/link";
import { SectionNav, SUPPORT_LINKS } from "../../components/SectionNav";
import { Shell } from "../../components/Shell";
import c from "../../components/content.module.css";
import ui from "../../components/ui.module.css";
import { api, call, useApiData } from "../../lib/api";

const loadSummary = () => call(() => api.GET("/api/v1/staff/support/summary"));

export default function SupportPage() {
  return (
    <Shell>
      <h1 className={ui.title}>Support</h1>
      <SectionNav label="Support" links={SUPPORT_LINKS} />
      <Summary />
    </Shell>
  );
}

function Stat({ value, label, href }: { value: number | null; label: string; href: string }) {
  if (value === null) return null;
  return (
    <Link href={href} className={c.stat}>
      <strong>{value}</strong>
      {label}
    </Link>
  );
}

function Summary() {
  const { data, error } = useApiData(loadSummary);
  if (error) return <p className={ui.error}>{error}</p>;
  if (!data) return <p className={ui.muted}>Loading…</p>;
  return (
    <>
      <h2 className={ui.subtitle}>Messages</h2>
      <div className={c.stats}>
        <Stat
          value={data.tickets_open}
          label="waiting for a reply"
          href="/support/tickets?status=open"
        />
        <Stat value={data.tickets_mine} label="assigned to me" href="/support/tickets?mine=1" />
        <Stat
          value={data.tickets_waiting}
          label="waiting for the customer"
          href="/support/tickets?status=waiting"
        />
      </div>
      {data.returns_requested !== null && (
        <>
          <h2 className={ui.subtitle}>Returns</h2>
          <div className={c.stats}>
            <Stat
              value={data.returns_requested}
              label="to decide"
              href="/support/returns?status=requested"
            />
            <Stat
              value={data.returns_to_receive}
              label="on their way back"
              href="/support/returns?status=approved"
            />
            <Stat
              value={data.returns_to_inspect}
              label="to inspect"
              href="/support/returns?status=received"
            />
            <Stat
              value={data.returns_to_complete}
              label="to refund or exchange"
              href="/support/returns?status=inspected"
            />
          </div>
        </>
      )}
      {data.refunds_waiting !== null && (
        <div className={c.stats}>
          <Stat
            value={data.refunds_waiting}
            label="refunds waiting for approval"
            href="/orders/refunds"
          />
        </div>
      )}
    </>
  );
}
