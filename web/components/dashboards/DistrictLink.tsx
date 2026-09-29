import Link from "next/link";
import { toTitleCase } from "@/lib/format";

/** Link to a district profile page. */
export function DistrictLink({ lgd, name }: { lgd: number | string; name: string }) {
  return <Link href={`/districts/${lgd}`}>{toTitleCase(name)}</Link>;
}
