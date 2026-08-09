import { PageHeader } from "@/components/layout/PageHeader";
import { ComingSoon } from "@/components/layout/ComingSoon";

export default function AdministrationPage() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title="Administration"
        description="Users, roles, fields, facilities, and system settings."
      />
      <ComingSoon module="Administration" />
    </div>
  );
}
