import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { legalDocs } from "@/lib/legal";

export function generateStaticParams() {
  return Object.keys(legalDocs).map((doc) => ({ doc }));
}

export function generateMetadata({ params }: { params: { doc: string } }): Metadata {
  const d = legalDocs[params.doc];
  return d ? { title: d.title, alternates: { canonical: `/legal/${params.doc}` } } : {};
}

export default function LegalPage({ params }: { params: { doc: string } }) {
  const d = legalDocs[params.doc];
  if (!d) notFound();
  return (
    <div className="container-x max-w-3xl py-10">
      <h1 className="text-3xl font-extrabold">{d.title}</h1>
      <div className="mt-8 space-y-6">
        {d.sections.map((s) => (
          <section key={s.heading} className="surface p-6">
            <h2 className="font-bold">{s.heading}</h2>
            <p className="mt-2 text-sm text-muted">{s.body}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
