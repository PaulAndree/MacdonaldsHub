import { es } from "../../i18n/es";
import Kpi from "../../ui/Kpi";
import { AmountText, Unknown, formatRate } from "../../ui/values";
import type { ChannelMetrics, Metrics } from "./queries";

const t = es.metrics;

/**
 * The figures of one channel. An amount that is missing for some incidents is shown with its total
 * and flagged as incomplete; it is never treated as zero and never shown as a clean total.
 */
export default function ChannelPanel({ channel, criteria }: { channel: ChannelMetrics; criteria: Metrics["criteria"] }) {
  const empty = channel.claimedCount === 0;
  const incomplete = channel.incompleteCount > 0;
  const headingId = `channel-${channel.channel}`;
  return (
    <section className="card" aria-labelledby={headingId}>
      <h2 id={headingId}>{t.channels[channel.channel]}</h2>
      <div className="kpis kpis--five">
        <Kpi accent label={t.kpi.claimed} value={channel.claimedCount} />
        <Kpi
          label={t.kpi.claimedAmount}
          value={
            <>
              <AmountText value={channel.claimedAmount} unknown={t.noData} />
              {incomplete && <span className="pill pill--review incomplete-flag">{t.incomplete}</span>}
            </>
          }
          note={incomplete ? t.incompleteNote(channel.incompleteCount) : undefined}
        />
        <Kpi label={t.kpi.recovered} value={channel.recoveredCount} />
        <Kpi label={t.kpi.recoveredAmount} value={<AmountText value={channel.recoveredAmount} unknown={empty ? t.noData : t.noRecovery} />} />
        <Kpi
          label={t.kpi.rate}
          value={channel.recoveryRate === null ? <Unknown>{t.rateUnknown}</Unknown> : formatRate(channel.recoveryRate)}
          note={criteria.status === "example" ? t.rateExample : undefined}
        />
      </div>
    </section>
  );
}
