/** Runs a workspace change, shows any error, then reloads the workspace. */
export type RunAction = (change: () => Promise<unknown>) => Promise<void>;

export type WorkspaceCardProps = { workspace: any; workspaceId: string; canEdit: boolean; run: RunAction };
