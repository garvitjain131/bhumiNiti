/** Kinds of call the Innovation Portal can publish. */
export const CALL_KIND_LABELS: Record<string, string> = {
  institutional_grant: "Institutional grant",
  individual_grant: "Individual grant",
  hackathon: "Hackathon",
  pilot: "Pilot",
  competition: "Knowledge competition",
};

/** Grant workflow stages, in order (an application can also be "rejected" at any point). */
export const APPLICATION_STAGES = [
  "submitted", "under_review", "shortlisted", "awarded", "advance_released", "review_1", "review_2", "final_report", "completed",
];

export const CONTRIBUTION_KINDS = ["finding", "paper", "dataset", "case_study", "policy_note"];
export const FINDING_DIRECTIONS = ["positive", "negative", "no clear effect", "mixed", "descriptive"];
