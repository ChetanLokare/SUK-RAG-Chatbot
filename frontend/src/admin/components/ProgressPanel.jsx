export default function ProgressPanel({ events }) {
  const pages = events.filter(e => e.event === "pdf_page_done");

  return (
    <div>
      <h3>Live Ingestion Progress</h3>

      {events.map((e, i) => (
        <div key={i}>
          {e.event === "start" && <>Started ({e.requested})</>}
          {e.event === "ingested" && <>✔ Ingested {e.id}</>}
          {e.event === "failed" && <>❌ {e.id}: {e.error}</>}
          {e.event === "pdf_page_start" && (
            <>📄 PDF {e.page}/{e.total}</>
          )}
        </div>
      ))}
    </div>
  );
}
