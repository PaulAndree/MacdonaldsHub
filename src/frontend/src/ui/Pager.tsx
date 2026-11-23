import { es } from "../i18n/es";

/** "Rows 1 to 50 of 500" with previous and next. The total is always stated: nothing is cut off silently. */
export default function Pager({
  page,
  total,
  pageSize,
  onPage,
  label,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPage: (page: number) => void;
  label: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <nav aria-label={label} className="pager">
      <p role="status">
        {es.review.showing(from, to, total)} · {es.review.pageOf(page, pages)}
      </p>
      <button type="button" className="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        {es.review.previous}
      </button>{" "}
      <button type="button" className="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        {es.review.next}
      </button>
    </nav>
  );
}
