import { createContext, useContext } from "react";

interface WorkspaceSelection {
  organizationId: string;
  selectOrganization: (organizationId: string) => void;
}

export const WorkspaceSelectionContext = createContext<WorkspaceSelection>({
  organizationId: "",
  selectOrganization: () => undefined,
});

export function useWorkspaceSelection(): WorkspaceSelection {
  return useContext(WorkspaceSelectionContext);
}
