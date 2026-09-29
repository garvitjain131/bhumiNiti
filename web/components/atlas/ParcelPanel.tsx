import Link from "next/link";
import { SignInLink } from "@/components/auth/SignInLink";
import { Card, DataLabel, ErrorAlert, Spinner } from "@/components/ui";
import { formatNumber } from "@/lib/format";

/** Side panel for a clicked cadastral parcel: village-level summary of the synthetic land records. */
export function ParcelPanel({ parcel }: { parcel: any }) {
  return (
    <Card title={`Parcel · ${parcel.village ?? ""}`}>
      {parcel.loading ? <Spinner /> : parcel.error ? <ErrorAlert error={parcel.error} /> : (
        <div className="text-sm">
          <p className="mb-2"><DataLabel label="SYNTHETIC" /> Real parcel geometry; land-record values are synthetic.</p>
          {parcel.note ? <p>{parcel.note}. <SignInLink /></p> : (
            <dl className="grid grid-cols-2 gap-y-1">
              <dt className="text-muted">Parcel area</dt><dd>{formatNumber(Number(parcel.area), 3)} ha</dd>
              <dt className="text-muted">Village parcels</dt><dd>{formatNumber(parcel.parcels)}</dd>
              <dt className="text-muted">Village area</dt><dd>{formatNumber(parcel.area_ha)} ha</dd>
              <dt className="text-muted">Women owners</dt><dd>{formatNumber(parcel.female_owner_share * 100)}%</dd>
              <dt className="text-muted">Mortgaged</dt><dd>{formatNumber(parcel.mortgaged_share * 100)}%</dd>
              <dt className="text-muted">Mutations pending</dt><dd>{parcel.mutation_pending ?? "<5 (suppressed)"}</dd>
              <dt className="text-muted">Disputes pending</dt><dd>{parcel.dispute_pending ?? "<5 (suppressed)"}</dd>
            </dl>
          )}
          {parcel.record_level_access === false && (
            <p className="mt-2 text-xs text-muted">
              Record-level data needs an approved access request (<Link href="/data?tab=land-records">Data &amp; APIs</Link>).
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
