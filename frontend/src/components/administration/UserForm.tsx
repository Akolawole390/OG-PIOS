"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { listRoles, type Role, type UserCreatePayload, type UserUpdatePayload } from "@/lib/api";

export type UserFormValues = {
  email: string;
  full_name: string;
  password: string;
  role_id: string;
  is_active: boolean;
};

const EMPTY_VALUES: UserFormValues = {
  email: "",
  full_name: "",
  password: "",
  role_id: "",
  is_active: true,
};

type UserFormProps =
  | {
      mode: "create";
      initialValues?: Partial<UserFormValues>;
      submitLabel: string;
      onSubmit: (payload: UserCreatePayload) => Promise<void>;
    }
  | {
      mode: "edit";
      initialValues?: Partial<UserFormValues>;
      submitLabel: string;
      onSubmit: (payload: UserUpdatePayload) => Promise<void>;
    };

export function UserForm(props: UserFormProps) {
  const { mode, initialValues, submitLabel, onSubmit } = props;
  const [values, setValues] = useState<UserFormValues>({ ...EMPTY_VALUES, ...initialValues });
  const [roles, setRoles] = useState<Role[]>([]);
  const [errors, setErrors] = useState<Partial<Record<keyof UserFormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    listRoles()
      .then(setRoles)
      .catch(() => undefined);
  }, []);

  function update<K extends keyof UserFormValues>(key: K, value: UserFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const nextErrors: Partial<Record<keyof UserFormValues, string>> = {};
    if (mode === "create" && !values.email.trim()) nextErrors.email = "Email is required.";
    if (!values.full_name.trim()) nextErrors.full_name = "Full name is required.";
    if (mode === "create" && values.password.length < 8) {
      nextErrors.password = "Password must be at least 8 characters.";
    }
    if (!values.role_id) nextErrors.role_id = "Role is required.";
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      if (mode === "create") {
        const payload: UserCreatePayload = {
          email: values.email.trim(),
          full_name: values.full_name.trim(),
          password: values.password,
          role_id: Number(values.role_id),
          is_active: values.is_active,
        };
        await onSubmit(payload);
      } else {
        const payload: UserUpdatePayload = {
          full_name: values.full_name.trim(),
          role_id: Number(values.role_id),
          is_active: values.is_active,
        };
        await onSubmit(payload);
      }
    } catch {
      setSubmitError("Unable to save this user. Check the form and try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-lg flex-col gap-5">
      {mode === "create" ? (
        <Field label="Email" error={errors.email}>
          <input
            type="email"
            value={values.email}
            onChange={(e) => update("email", e.target.value)}
            className={inputClass}
          />
        </Field>
      ) : null}

      <Field label="Full Name" error={errors.full_name}>
        <input
          value={values.full_name}
          onChange={(e) => update("full_name", e.target.value)}
          className={inputClass}
        />
      </Field>

      {mode === "create" ? (
        <Field label="Temporary Password" error={errors.password}>
          <input
            type="password"
            value={values.password}
            onChange={(e) => update("password", e.target.value)}
            className={inputClass}
          />
        </Field>
      ) : null}

      <Field label="Role" error={errors.role_id}>
        <select value={values.role_id} onChange={(e) => update("role_id", e.target.value)} className={inputClass}>
          <option value="">Select a role…</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
      </Field>

      <label className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
        <input
          type="checkbox"
          checked={values.is_active}
          onChange={(e) => update("is_active", e.target.checked)}
          className="h-4 w-4 rounded border-zinc-300 dark:border-zinc-700"
        />
        Active
      </label>

      {submitError ? <p className="text-sm text-red-600 dark:text-red-400">{submitError}</p> : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-fit rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        {isSubmitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}

const inputClass =
  "mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
      {label}
      {children}
      {error ? <span className="mt-1 block text-xs font-normal text-red-600 dark:text-red-400">{error}</span> : null}
    </label>
  );
}
