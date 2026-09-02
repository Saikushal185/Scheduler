"use client";

import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, Upload, XCircle } from "lucide-react";
import * as React from "react";

import { usePageMeta } from "@/components/layout/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, LoadingState } from "@/components/ui/feedback";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyRow, TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { ApiError, api } from "@/lib/api";
import { useColumnMappings, useUploads } from "@/lib/queries";
import type { ImportResponse, ValidationResponse } from "@/lib/types";

export default function UploadPage() {
  usePageMeta(
    "Data / Excel Upload",
    "Upload .xlsx or .csv files - sheets are detected, validated and imported",
  );

  const { notify } = useToast();
  const client = useQueryClient();
  const { data: uploads } = useUploads();
  const { data: mappings, isLoading: mappingsLoading } = useColumnMappings();

  const [file, setFile] = React.useState<File | null>(null);
  const [busy, setBusy] = React.useState<"validate" | "import" | null>(null);
  const [validation, setValidation] = React.useState<ValidationResponse | null>(null);
  const [imported, setImported] = React.useState<ImportResponse | null>(null);
  const [error, setError] = React.useState<ApiError | Error | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  function reset(next: File | null) {
    setFile(next);
    setValidation(null);
    setImported(null);
    setError(null);
  }

  async function run(action: "validate" | "import") {
    if (!file) return;
    setBusy(action);
    setError(null);
    setImported(null);
    try {
      if (action === "validate") {
        const result = await api.upload<ValidationResponse>("/uploads/validate", file);
        setValidation(result);
        notify(
          result.is_valid
            ? "File is valid and ready to import."
            : "Validation found problems - see the details below.",
          result.is_valid ? "success" : "error",
        );
      } else {
        const result = await api.upload<ImportResponse>("/uploads/import", file);
        setImported(result);
        setValidation(null);
        notify(
          `Imported ${result.total_created} new and ${result.total_updated} updated row(s).`,
        );
        client.invalidateQueries();
      }
    } catch (err) {
      setError(err as Error);
      if (err instanceof ApiError && err.details) {
        const details = err.details as ValidationResponse;
        if (details?.sheets) setValidation(details);
      }
      notify(err instanceof Error ? err.message : "Upload failed", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardContent className="pt-5">
          <div
            className="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-[var(--color-border)] bg-slate-50/60 px-6 py-10 text-center"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              const dropped = event.dataTransfer.files?.[0];
              if (dropped) reset(dropped);
            }}
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--color-brand-light)] text-[var(--color-brand-dark)]">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">
                {file ? file.name : "Drop a spreadsheet here, or browse"}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                .xlsx and .csv · one sheet per entity · sheets are detected automatically
              </p>
            </div>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={(event) => reset(event.target.files?.[0] ?? null)}
            />
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()}>
                Choose file
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!file || busy !== null}
                onClick={() => run("validate")}
              >
                {busy === "validate" ? "Validating..." : "Validate only"}
              </Button>
              <Button size="sm" disabled={!file || busy !== null} onClick={() => run("import")}>
                <Upload className="h-3.5 w-3.5" />
                {busy === "import" ? "Importing..." : "Validate & import"}
              </Button>
            </div>
          </div>

          {error && !validation ? (
            <Alert tone="danger" title="Upload failed" className="mt-4">
              {error.message}
            </Alert>
          ) : null}

          {imported ? (
            <div className="mt-4 space-y-3">
              <Alert tone="success" title={`Imported ${imported.filename}`}>
                {imported.total_created} created · {imported.total_updated} updated ·{" "}
                {imported.total_failed} failed · {imported.free_slots_recalculated} free
                slots recalculated
              </Alert>
              <Table>
                <THead>
                  <TR>
                    <TH>Sheet</TH>
                    <TH>Detected as</TH>
                    <TH>Rows</TH>
                    <TH>Created</TH>
                    <TH>Updated</TH>
                    <TH>Failed</TH>
                  </TR>
                </THead>
                <TBody>
                  {imported.summaries.map((summary, index) => (
                    <TR key={index}>
                      <TD>{summary.sheet_name}</TD>
                      <TD>
                        <Badge tone="brand">{summary.dataset}</Badge>
                      </TD>
                      <TD>{summary.rows_total}</TD>
                      <TD className="text-[var(--color-success)]">{summary.created}</TD>
                      <TD>{summary.updated}</TD>
                      <TD className={summary.failed ? "text-[var(--color-danger)]" : ""}>
                        {summary.failed}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </div>
          ) : null}

          {validation ? (
            <div className="mt-4 space-y-3">
              <Alert
                tone={validation.is_valid ? "success" : "danger"}
                title={
                  validation.is_valid
                    ? "All sheets passed validation"
                    : "Validation errors must be fixed before importing"
                }
              >
                {validation.filename} · {validation.sheets.length} sheet(s)
              </Alert>
              {validation.sheets.map((sheet) => (
                <Card key={sheet.sheet_name}>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      {sheet.is_valid ? (
                        <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
                      ) : (
                        <XCircle className="h-4 w-4 text-[var(--color-danger)]" />
                      )}
                      <CardTitle>{sheet.sheet_name}</CardTitle>
                      {sheet.detected_dataset ? (
                        <Badge tone="brand">{sheet.detected_dataset}</Badge>
                      ) : (
                        <Badge tone="danger">Unrecognised</Badge>
                      )}
                      <span className="text-[11px] text-slate-400">
                        {sheet.row_count} row(s)
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {sheet.missing_required_columns.length ? (
                      <Alert tone="danger" title="Missing required columns">
                        {sheet.missing_required_columns.join(", ")}
                      </Alert>
                    ) : null}
                    {sheet.errors.length ? (
                      <div className="rounded-lg border border-[var(--color-border)]">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Row</TH>
                              <TH>Column</TH>
                              <TH>Problem</TH>
                            </TR>
                          </THead>
                          <TBody>
                            {sheet.errors.slice(0, 25).map((issue, index) => (
                              <TR key={index}>
                                <TD>{issue.row ?? "-"}</TD>
                                <TD>{issue.column ?? "-"}</TD>
                                <TD className="text-[var(--color-danger)]">
                                  {issue.message}
                                </TD>
                              </TR>
                            ))}
                          </TBody>
                        </Table>
                      </div>
                    ) : null}
                    {sheet.warnings.length ? (
                      <Alert tone="warning" title={`${sheet.warnings.length} warning(s)`}>
                        <ul className="list-disc pl-4">
                          {sheet.warnings.slice(0, 5).map((issue, index) => (
                            <li key={index}>
                              Row {issue.row}: {issue.message}
                            </li>
                          ))}
                        </ul>
                      </Alert>
                    ) : null}
                    {sheet.unmapped_columns.length ? (
                      <p className="text-[11px] text-slate-400">
                        Ignored columns: {sheet.unmapped_columns.join(", ")}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Tabs defaultValue="mappings">
        <TabsList>
          <TabsTrigger value="mappings">Accepted columns</TabsTrigger>
          <TabsTrigger value="history">Upload history</TabsTrigger>
        </TabsList>

        <TabsContent value="mappings">
          <Card>
            <CardContent className="px-0 pb-0 pt-2">
              {mappingsLoading ? (
                <LoadingState />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Dataset</TH>
                      <TH>Required columns</TH>
                      <TH>Optional columns</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {(mappings ?? []).map((mapping) => (
                      <TR key={mapping.dataset}>
                        <TD className="align-top">
                          <Badge tone="brand">{mapping.dataset}</Badge>
                        </TD>
                        <TD className="align-top">
                          <div className="flex flex-wrap gap-1">
                            {mapping.required.map((column) => (
                              <span
                                key={column}
                                className="rounded bg-[var(--color-danger-light)] px-1.5 py-0.5 text-[11px] text-[var(--color-danger)]"
                              >
                                {column}
                              </span>
                            ))}
                          </div>
                        </TD>
                        <TD className="align-top">
                          <div className="flex flex-wrap gap-1">
                            {mapping.optional.map((column) => (
                              <span
                                key={column}
                                className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600"
                              >
                                {column}
                              </span>
                            ))}
                          </div>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardContent className="px-0 pb-0 pt-2">
              <Table>
                <THead>
                  <TR>
                    <TH>File</TH>
                    <TH>Status</TH>
                    <TH>Rows</TH>
                    <TH>Imported</TH>
                    <TH>Failed</TH>
                  </TR>
                </THead>
                <TBody>
                  {uploads?.length ? (
                    uploads.map((upload) => (
                      <TR key={upload.id}>
                        <TD className="font-medium text-slate-800">
                          {upload.original_filename}
                        </TD>
                        <TD>
                          <Badge
                            tone={
                              upload.status === "IMPORTED"
                                ? "success"
                                : upload.status === "FAILED"
                                  ? "danger"
                                  : "neutral"
                            }
                          >
                            {upload.status}
                          </Badge>
                        </TD>
                        <TD>{upload.rows_total}</TD>
                        <TD>{upload.rows_imported}</TD>
                        <TD>{upload.rows_failed}</TD>
                      </TR>
                    ))
                  ) : (
                    <EmptyRow colSpan={5} message="No files uploaded yet." />
                  )}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
