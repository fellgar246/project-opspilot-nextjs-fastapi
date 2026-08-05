"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAuth } from "@/features/auth/AuthProvider";
import { getDefaultApiBaseUrl } from "@/lib/auth-api";
import {
  createIncident,
  fetchServices,
  type IncidentSeverity,
} from "@/lib/incidents-api";

const createSchema = z.object({
  title: z.string().min(1, "Title is required").max(500),
  description: z.string().min(1, "Description is required"),
  severity: z.enum(["sev1", "sev2", "sev3", "sev4"]),
  service_ids: z.array(z.string()).min(1, "Select at least one service"),
  started_at: z.string().min(1, "Start time is required"),
});

type CreateFormValues = z.infer<typeof createSchema>;

export function CreateIncidentForm() {
  const { can } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const apiBaseUrl = getDefaultApiBaseUrl();
  const [formError, setFormError] = useState<string | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["services"],
    queryFn: () => fetchServices(apiBaseUrl),
  });

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      title: "",
      description: "",
      severity: "sev3",
      service_ids: [],
      started_at: new Date().toISOString().slice(0, 16),
    },
  });

  const selectedServices = watch("service_ids");

  const mutation = useMutation({
    mutationFn: (values: CreateFormValues) =>
      createIncident(apiBaseUrl, {
        ...values,
        severity: values.severity as IncidentSeverity,
        started_at: new Date(values.started_at).toISOString(),
        source: "manual",
      }),
    onSuccess: (incident) => {
      void queryClient.invalidateQueries({ queryKey: ["incidents"] });
      router.push(`/incidents/${incident.id}`);
    },
    onError: (error: Error) => {
      setFormError(error.message);
    },
  });

  if (!can("create_incidents")) {
    return <p role="status">You do not have permission to create incidents.</p>;
  }

  const onSubmit = handleSubmit((values) => {
    setFormError(null);
    mutation.mutate(values);
  });

  const toggleService = (serviceId: string) => {
    const next = selectedServices.includes(serviceId)
      ? selectedServices.filter((id) => id !== serviceId)
      : [...selectedServices, serviceId];
    setValue("service_ids", next, { shouldValidate: true });
  };

  return (
    <form className="incident-form" onSubmit={onSubmit}>
      <h1>Create incident</h1>
      {formError ? <p role="alert">{formError}</p> : null}

      <label>
        Title
        <input type="text" {...register("title")} />
        {errors.title ? <span role="alert">{errors.title.message}</span> : null}
      </label>

      <label>
        Description
        <textarea rows={4} {...register("description")} />
        {errors.description ? <span role="alert">{errors.description.message}</span> : null}
      </label>

      <label>
        Severity
        <select {...register("severity")}>
          <option value="sev1">SEV1</option>
          <option value="sev2">SEV2</option>
          <option value="sev3">SEV3</option>
          <option value="sev4">SEV4</option>
        </select>
      </label>

      <label>
        Started at
        <input type="datetime-local" {...register("started_at")} />
        {errors.started_at ? <span role="alert">{errors.started_at.message}</span> : null}
      </label>

      <fieldset>
        <legend>Affected services</legend>
        {servicesQuery.isLoading ? <p role="status">Loading services…</p> : null}
        {servicesQuery.isError ? (
          <p role="alert">Unable to load services.</p>
        ) : (
          (servicesQuery.data ?? []).map((service) => (
            <label key={service.id} className="checkbox-label">
              <input
                type="checkbox"
                checked={selectedServices.includes(service.id)}
                onChange={() => toggleService(service.id)}
              />
              {service.name} ({service.environment})
            </label>
          ))
        )}
        {errors.service_ids ? <span role="alert">{errors.service_ids.message}</span> : null}
      </fieldset>

      <div className="form-actions">
        <button type="submit" disabled={isSubmitting || mutation.isPending}>
          {isSubmitting || mutation.isPending ? "Creating…" : "Create incident"}
        </button>
        <Link href="/incidents">Cancel</Link>
      </div>
    </form>
  );
}
