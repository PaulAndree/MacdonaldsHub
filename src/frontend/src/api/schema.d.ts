// Generated from docs/api/openapi.yaml by scripts/contract.mjs. Do not edit by hand.
export interface paths {
    "/api/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Identity, role, environment and permissions of the signed-in user
         * @description Lets the interface show the session and filter its navigation. Authorization is still enforced by the API on every operation.
         */
        get: operations["getSession"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Register a batch and get a temporary upload permission
         * @description Fails with 409 when the user already has an unconfirmed batch (one per user).
         */
        post: operations["createBatch"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/pending": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * The user's unconfirmed batch, if any
         * @description Used to show the notice of a batch under review when the user returns. There is no expiry.
         */
        get: operations["getPendingBatch"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/discard-unconfirmed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Discard all of the user's unconfirmed batches
         * @description Used by the Cerrar sesión button. It discards batches only and does not end the Google session.
         */
        post: operations["discardUnconfirmedBatches"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        /** State of a batch */
        get: operations["getBatch"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/uploaded": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record that the upload finished and request processing */
        post: operations["completeUpload"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/rows": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        /**
         * Rows of a prepared batch with their class and reason
         * @description The classification comes from the backend; the interface never recomputes it.
         */
        get: operations["listBatchRows"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/excluded-report": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        /**
         * XLSX report of the excluded rows with their reasons
         * @description Lets the administrator correct and upload again (RF-20).
         */
        get: operations["downloadExcludedReport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/confirmation-summary": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        /** What confirming this batch will do */
        get: operations["getConfirmationSummary"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm the reviewed batch
         * @description Idempotent. There is no undo and emails cannot be cancelled afterwards.
         */
        post: operations["confirmBatch"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/batches/{batchId}/discard": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel an unconfirmed batch
         * @description Allowed only before confirmation. Deletes the file and the prepared rows.
         */
        post: operations["discardBatch"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List confirmed incidents with filters */
        get: operations["listIncidents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * XLSX export of the incidents that match the filters
         * @description Absent values stay explicit (Sin sucursal, unknown amount); they are never exported as zero.
         */
        get: operations["exportIncidents"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/manual/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check a manual entry by provider and order ID before reviewing it
         * @description Never creates an incident.
         */
        post: operations["checkManualIncident"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/manual": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Save a manual entry after the administrator reviewed and confirmed it
         * @description A manual Uber Eats or Just Eat entry generates its email (decision P-12): the incident is
         *     saved as `pending_send` together with one pending email, in the same transaction, and
         *     nothing is sent by this operation. A Glovo entry generates no email and is claimed by hand.
         */
        post: operations["createManualIncident"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/{incidentId}": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        /** Detail and history of an incident */
        get: operations["getIncident"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/{incidentId}/claim": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark an incident without email as claimed through an external channel
         * @description Applies to an incident in `imported_no_email` (Glovo, or a manual entry). The channel used to
         *     claim is pending decision P-11 and is not recorded.
         */
        post: operations["claimGlovoIncident"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/{incidentId}/result": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record the result and the explicit recovered amount, partial or full
         * @description Resolved does not imply the whole claimed amount was recovered.
         */
        post: operations["recordIncidentResult"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/incidents/{incidentId}/corrections": {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Correct a recorded result, keeping the history
         * @description Does not undo the import and does not affect any email.
         */
        post: operations["correctIncidentResult"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Dashboard figures, always stating the date used
         * @description Criteria decided by the administrator (P-04). A claim is an incident with a claim date and a
         *     recovery is an incident marked `resolved`. The recovery rate is recoveries divided by claims,
         *     by number, and is `null` when there are no claims or the recovery date is the one used. Known
         *     amounts are added up and the missing ones are counted; an absent amount is never counted as zero.
         */
        get: operations["getMetrics"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/branches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Branch names, to filter incidents
         * @description Read-only list for any role that reads incidents. The technical team maintains the branches; the interface has no screen for it.
         */
        get: operations["listBranchOptions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/email-queue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Email states, reasons, totals and the global pause
         * @description Each email has one attempt; at least 30 seconds separate the start of consecutive attempts.
         */
        get: operations["getEmailQueue"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/email-queue/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Pause the queue globally and persistently
         * @description Prevents new attempts. An attempt already started may finish; nothing is cancelled.
         */
        post: operations["pauseEmailQueue"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/email-queue/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Resume the queue
         * @description New attempts start again, still spaced by at least 30 seconds. Emails already in Error are not retried.
         */
        post: operations["resumeEmailQueue"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * @description Decimal amount in EUR as a string. Keeps the source decimals; sign is kept as received.
         * @example 12.50
         * @example 0.1234
         * @example -3.00
         */
        Amount: string;
        /** @description An `Amount`, or `null` when the source has no value. `null` is never zero. */
        OptionalAmount: components["schemas"]["Amount"] | null;
        /**
         * @description Incident date as `YYYY-MM-DD`.
         * @example 2026-10-12
         */
        IncidentDate: string;
        /**
         * @description Optional `HH:MM` incident time in Europe/Madrid. `null` when the source has no time.
         * @example 20:22
         * @example null
         */
        IncidentTime: string | null;
        /**
         * Format: date-time
         * @description A UTC instant. The interface presents it in Europe/Madrid time.
         */
        Timestamp: string;
        /**
         * @description Lowercase provider. Only `uber eats` and `just eat` generate email.
         * @enum {string}
         */
        Provider: "uber eats" | "just eat" | "glovo";
        /** @enum {string} */
        Role: "administrator" | "global_manager";
        /** @enum {string} */
        Environment: "local" | "test" | "production";
        /**
         * @description Lifecycle of a batch. `uploaded`, `processing` and `in_review` are unconfirmed.
         * @enum {string}
         */
        BatchState: "uploaded" | "processing" | "in_review" | "rejected" | "discarded" | "confirmed" | "completed";
        /**
         * @description Exclusive classification produced by the backend for each row.
         * @enum {string}
         */
        RowClass: "new" | "duplicate" | "conflict" | "error";
        /**
         * @description Incident states. There is no transition from `send_error` back to `pending_send`.
         * @enum {string}
         */
        IncidentStatus: "imported_no_email" | "pending_send" | "claimed" | "send_error" | "resolved" | "rejected";
        /** @enum {string} */
        EmailState: "pending" | "sending" | "sent" | "error";
        /** @description The business fields of an incident, as in the XLSX contract. */
        IncidentCore: {
            provider: components["schemas"]["Provider"];
            /** @description Alphanumeric text kept exactly as received. */
            orderId: string;
            incidentDate: components["schemas"]["IncidentDate"];
            incidentTime: components["schemas"]["IncidentTime"];
            /** @description Lowercase branch, or `null` for an incident without branch ("Sin sucursal"). */
            branch: string | null;
            claimAmount: components["schemas"]["OptionalAmount"];
            providerCosts: components["schemas"]["OptionalAmount"];
            total: components["schemas"]["OptionalAmount"];
            description: string | null;
        };
        Error: {
            /** @description Stable machine-readable code, for example `not_authenticated`, `not_authorized`, `batch_discarded`. */
            code: string;
            /** @description Message intended for the user, in Spanish. */
            message: string;
            details?: {
                [key: string]: unknown;
            };
        };
        /**
         * @description Actions a role allows. Hiding an action in the interface never replaces API authorization.
         * @enum {string}
         */
        Permission: "import" | "confirm" | "incidents_read" | "incidents_write" | "metrics_read" | "queue_control";
        Session: {
            /** @description Stable identifier of the authenticated user. */
            identifier: string;
            email: string | null;
            role: components["schemas"]["Role"];
            environment: components["schemas"]["Environment"];
            permissions: components["schemas"]["Permission"][];
        };
        /** @description SHA-256 of the uploaded file. The confirmation is bound to this reviewed version. */
        Sha256: string;
        /** @description Temporary create-only permission to upload one file directly to storage. */
        UploadGrant: {
            url: string;
            /** @enum {string} */
            method: "PUT";
            headers: {
                [key: string]: string;
            };
            expiresAt: components["schemas"]["Timestamp"];
        };
        ClassTotals: {
            new: number;
            duplicate: number;
            conflict: number;
            error: number;
        };
        /** @description Counts of a prepared batch. Nothing here is definitive until the batch is confirmed. */
        BatchSummary: {
            totals: components["schemas"]["ClassTotals"];
            incidentsToCreate: number;
            emailsToGenerate: number;
            /** @description Valid new incidents that generate no email (Glovo). */
            withoutEmail: number;
        };
        /** @description Structure rejection of the whole file (RF-02). */
        Rejection: {
            /** @enum {string} */
            reason: "missing_required_header" | "multiple_worksheets" | "corrupt_or_protected_file";
            /** @description For example the name of the missing header. */
            detail: string | null;
        };
        /** @description The file matches a previously confirmed one. It never replaces row-level deduplication. */
        IdenticalFileNotice: {
            confirmedBatchId: string;
            confirmedAt: components["schemas"]["Timestamp"];
        };
        Batch: {
            id: string;
            state: components["schemas"]["BatchState"];
            fileName: string;
            createdAt: components["schemas"]["Timestamp"];
            reviewedVersion: components["schemas"]["Sha256"] | null;
            rejection: components["schemas"]["Rejection"] | null;
            identicalFile: components["schemas"]["IdenticalFileNotice"] | null;
            summary: components["schemas"]["BatchSummary"] | null;
        };
        CreateBatchRequest: {
            fileName: string;
            sizeBytes: number;
        };
        BatchUpload: {
            batch: components["schemas"]["Batch"];
            upload: components["schemas"]["UploadGrant"];
        };
        /**
         * @description The values of a row as read from the file, kept as text so nothing is rounded or repaired.
         *     Provider and branch are already lowercase. An absent value is `null`.
         */
        RowFields: {
            provider: string | null;
            orderId: string | null;
            incidentDate: string | null;
            incidentTime: string | null;
            branch: string | null;
            claimAmount: string | null;
            providerCosts: string | null;
            total: string | null;
            description: string | null;
        };
        /** @description The existing incident compared with the file row, for a conflict. */
        Comparison: {
            existing: components["schemas"]["IncidentCore"];
            differingFields: string[];
        };
        Row: {
            rowNumber: number;
            class: components["schemas"]["RowClass"];
            /** @description Reason shown to the user for every excluded row; `null` for a new row. */
            reason: string | null;
            fields: components["schemas"]["RowFields"];
            comparison: components["schemas"]["Comparison"] | null;
            /** @description Row numbers of the other occurrences of the same key inside the file. */
            repeatedInFile: number[];
        };
        /**
         * @description One page of rows. `total` counts the rows that match the filter and `totalsByClass` counts the
         *     whole batch, so the totals are always present and no truncation is silent (RNF-01).
         */
        RowPage: {
            items: components["schemas"]["Row"][];
            page: number;
            pageSize: number;
            total: number;
            totalsByClass: components["schemas"]["ClassTotals"];
        };
        EmailTemplate: {
            subject: string;
            body: string;
            /** @description False while P-03 is pending; the text is then only an example. */
            isFinal: boolean;
            pendingDecision: string | null;
        };
        Recipient: {
            /**
             * @description Only the test recipient is allowed until real recipients are defined (P-01).
             * @enum {string}
             */
            kind: "test";
            label: string;
        };
        ConfirmationSummary: {
            batchId: string;
            reviewedVersion: components["schemas"]["Sha256"];
            incidentsToCreate: number;
            emailsToGenerate: number;
            withoutEmail: number;
            excluded: number;
            recipient: components["schemas"]["Recipient"];
            template: components["schemas"]["EmailTemplate"];
        };
        ConfirmRequest: {
            reviewedVersion: components["schemas"]["Sha256"];
        };
        ExcludedRow: {
            rowNumber: number;
            class: components["schemas"]["RowClass"];
            reason: string;
        };
        /** @description The stored result of a confirmation. Repeating a confirmation returns the same result. */
        ConfirmationResult: {
            batchId: string;
            confirmedAt: components["schemas"]["Timestamp"];
            createdIncidents: number;
            pendingEmails: number;
            withoutEmail: number;
            excluded: components["schemas"]["ExcludedRow"][];
            /** @description Rows that became duplicates between review and confirmation (RF-10). */
            excludedAtConfirmation: components["schemas"]["ExcludedRow"][];
            /** @description True when this response repeats a confirmation already stored. */
            alreadyConfirmed: boolean;
        };
        DiscardResult: {
            discarded: number;
            batchIds: string[];
        };
        /** @description A calendar date as `YYYY-MM-DD`, or `null` when it has not happened. Used for claim and recovery dates. */
        OptionalDate: string | null;
        /**
         * @description Claims by email and manual Glovo claims are always kept apart.
         * @enum {string}
         */
        Channel: "email" | "glovo";
        /** @enum {string} */
        ResultKind: "resolved" | "rejected";
        /** @description A confirmed incident. The incident, claim and recovery dates are three distinct values. */
        Incident: {
            id: string;
            /** @description The batch that created the incident, or `null` for a manual entry. */
            batchId: string | null;
            provider: components["schemas"]["Provider"];
            orderId: string;
            incidentDate: components["schemas"]["IncidentDate"];
            incidentTime: components["schemas"]["IncidentTime"];
            branch: string | null;
            claimAmount: components["schemas"]["OptionalAmount"];
            providerCosts: components["schemas"]["OptionalAmount"];
            total: components["schemas"]["OptionalAmount"];
            description: string | null;
            status: components["schemas"]["IncidentStatus"];
            channel: components["schemas"]["Channel"];
            claimDate: components["schemas"]["OptionalDate"];
            recoveryDate: components["schemas"]["OptionalDate"];
            recoveredAmount: components["schemas"]["OptionalAmount"];
            result: components["schemas"]["ResultKind"] | null;
        };
        IncidentPage: {
            items: components["schemas"]["Incident"][];
            page: number;
            pageSize: number;
            total: number;
        };
        /** @description Append-only history of an incident. Corrections do not revert the batch or any email. */
        HistoryEntry: {
            at: components["schemas"]["Timestamp"];
            /** @description A user, or `system`. */
            actor: string;
            /** @enum {string} */
            kind: "imported" | "email_result" | "claim" | "result" | "correction";
            /**
             * @description The value that changed. `previousValue` and `newValue` refer to it.
             * @enum {string}
             */
            field: "status" | "claimDate" | "result" | "recoveredAmount" | "recoveryDate";
            previousValue: string | null;
            newValue: string | null;
            reason: string | null;
        };
        IncidentDetail: {
            incident: components["schemas"]["Incident"];
            history: components["schemas"]["HistoryEntry"][];
        };
        /** @description Outcome of checking a manual entry by provider and order ID before it is reviewed. */
        ManualCheckResult: {
            /** @enum {string} */
            outcome: "new" | "duplicate" | "conflict";
            existing: components["schemas"]["IncidentCore"] | null;
            differingFields: string[];
        };
        /** @description Manual claim of a Glovo incident made outside the application. The channel is pending P-11. */
        ClaimRequest: {
            claimDate: components["schemas"]["IncidentDate"];
        };
        ResultRequest: {
            result: components["schemas"]["ResultKind"];
            recoveredAmount: components["schemas"]["OptionalAmount"];
            recoveryDate: components["schemas"]["OptionalDate"];
        };
        CorrectionRequest: {
            result: components["schemas"]["ResultKind"];
            recoveredAmount: components["schemas"]["OptionalAmount"];
            recoveryDate: components["schemas"]["OptionalDate"];
            reason: string;
        };
        ChannelMetrics: {
            channel: components["schemas"]["Channel"];
            claimedCount: number;
            claimedAmount: components["schemas"]["OptionalAmount"];
            recoveredCount: number;
            recoveredAmount: components["schemas"]["OptionalAmount"];
            /** @description Incidents in the figure that have no claim amount, so the sum is incomplete. */
            incompleteCount: number;
            /** @description Recoveries over claims by number, with four decimals. `null` when there are no claims or the recovery date is the one used. */
            recoveryRate: string | null;
        };
        BreakdownRow: {
            provider: components["schemas"]["Provider"];
            /** @description `null` is shown as "Sin sucursal". */
            branch: string | null;
            claimedCount: number;
            claimedAmount: components["schemas"]["OptionalAmount"];
            recoveredCount: number;
            recoveredAmount: components["schemas"]["OptionalAmount"];
            incompleteCount: number;
        };
        PendingClaim: {
            incidentId: string;
            provider: components["schemas"]["Provider"];
            claimDate: components["schemas"]["IncidentDate"];
            /** @description Calendar days since the claim, in Europe/Madrid time. There is no threshold. */
            ageDays: number;
        };
        MetricsWarning: {
            /** @enum {string} */
            code: "incomplete_amounts" | "no_data";
            message: string;
            count: number;
        };
        CriteriaStatus: {
            /** @enum {string} */
            status: "example" | "approved";
            pendingDecision: string | null;
        };
        Metrics: {
            environment: components["schemas"]["Environment"];
            /**
             * @description The date every figure and filter uses. It is always stated to the user.
             * @enum {string}
             */
            dateKind: "incident" | "claim" | "recovery";
            criteria: components["schemas"]["CriteriaStatus"];
            channels: components["schemas"]["ChannelMetrics"][];
            breakdown: components["schemas"]["BreakdownRow"][];
            pendingClaims: components["schemas"]["PendingClaim"][];
            warnings: components["schemas"]["MetricsWarning"][];
        };
        Branch: {
            id: string;
            /** @description Lowercase branch name, as it must appear in the XLSX. */
            name: string;
            active: boolean;
        };
        BranchList: {
            items: components["schemas"]["Branch"][];
        };
        QueueStatus: {
            /** @description Persistent. Pausing prevents new attempts; an attempt already started may finish. */
            paused: boolean;
            pausedAt: components["schemas"]["Timestamp"] | null;
            /** @description Attempts started and not finished. */
            inFlight: number;
            /**
             * @description False when nothing can be sent (no mail server, sender or test recipient configured, or a
             *     production environment without real recipients). The emails stay pending and none turns
             *     into an error because of it.
             */
            sendingAvailable: boolean;
            /** @description Why sending is unavailable, in Spanish, or `null` when it is available. */
            unavailableReason: string | null;
        };
        EmailTotals: {
            pending: number;
            sending: number;
            sent: number;
            error: number;
        };
        /** @description One email. It has a single attempt; there is no retry, resend or cancel. */
        QueueEntry: {
            id: string;
            incidentId: string;
            /** @description The batch that created the email, or `null` for the email of a manual entry. */
            batchId: string | null;
            orderId: string;
            provider: components["schemas"]["Provider"];
            state: components["schemas"]["EmailState"];
            /** @description Reason for an `error` state, shown to the user. */
            reason: string | null;
            /**
             * @description `interrupted_unverified` means the result could not be verified; it does not prove the
             *     email was not received.
             * @enum {string|null}
             */
            errorKind: "send_failed" | "interrupted_unverified" | null;
            startedAt: components["schemas"]["Timestamp"] | null;
            finishedAt: components["schemas"]["Timestamp"] | null;
            recipient: components["schemas"]["Recipient"];
        };
        /** @description A batch is completed when every email is `sent` or `error`. Completed does not mean all succeeded. */
        BatchEmailProgress: {
            batchId: string;
            completed: boolean;
            totals: components["schemas"]["EmailTotals"];
        };
        QueueView: {
            status: components["schemas"]["QueueStatus"];
            /**
             * @description Minimum seconds between the start of consecutive attempts.
             * @enum {integer}
             */
            minIntervalSeconds: 30;
            /** @enum {integer} */
            attemptsPerEmail: 1;
            nextEligibleAt: components["schemas"]["Timestamp"] | null;
            totals: components["schemas"]["EmailTotals"];
            batches: components["schemas"]["BatchEmailProgress"][];
            items: components["schemas"]["QueueEntry"][];
            page: number;
            pageSize: number;
            total: number;
        };
    };
    responses: {
        /** @description No valid session. */
        Unauthenticated: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description Authenticated but not authorized for this operation. */
        Forbidden: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
        /** @description The object does not exist. */
        NotFound: {
            headers: {
                [name: string]: unknown;
            };
            content: {
                "application/json": components["schemas"]["Error"];
            };
        };
    };
    parameters: {
        BatchId: string;
        Page: number;
        PageSize: number;
        IncidentId: string;
        FilterProvider: components["schemas"]["Provider"];
        /** @description A lowercase branch, or `none` for incidents without branch. */
        FilterBranch: string;
        FilterStatus: components["schemas"]["IncidentStatus"];
        /** @description Which date the range applies to. */
        DateKind: "incident" | "claim" | "recovery";
        DateFrom: components["schemas"]["IncidentDate"];
        DateTo: components["schemas"]["IncidentDate"];
        QueueState: components["schemas"]["EmailState"];
        QueueBatchId: string;
    };
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getSession: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The authenticated, authorized user. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Session"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    createBatch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateBatchRequest"];
            };
        };
        responses: {
            /** @description Batch created with its upload permission. */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BatchUpload"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            /** @description The user already has an unconfirmed batch. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    getPendingBatch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The unconfirmed batch. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Batch"];
                };
            };
            /** @description The user has no unconfirmed batch. */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    discardUnconfirmedBatches: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The batches that were discarded. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DiscardResult"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    getBatch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The batch. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Batch"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    completeUpload: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Processing was requested. */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Batch"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    listBatchRows: {
        parameters: {
            query?: {
                class?: components["schemas"]["RowClass"];
                page?: components["parameters"]["Page"];
                pageSize?: components["parameters"]["PageSize"];
            };
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description One page of rows. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RowPage"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    downloadExcludedReport: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The report file. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": string;
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    getConfirmationSummary: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The summary shown before the single confirm action. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConfirmationSummary"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    confirmBatch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConfirmRequest"];
            };
        };
        responses: {
            /** @description The stored confirmation result. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConfirmationResult"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description The batch cannot be confirmed in its current state. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
            /** @description The reviewed version does not match the uploaded file. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    discardBatch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                batchId: components["parameters"]["BatchId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The batch is now discarded. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Batch"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description A confirmed batch cannot be cancelled. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    listIncidents: {
        parameters: {
            query?: {
                provider?: components["parameters"]["FilterProvider"];
                /** @description A lowercase branch, or `none` for incidents without branch. */
                branch?: components["parameters"]["FilterBranch"];
                status?: components["parameters"]["FilterStatus"];
                /** @description Which date the range applies to. */
                dateKind?: components["parameters"]["DateKind"];
                from?: components["parameters"]["DateFrom"];
                to?: components["parameters"]["DateTo"];
                page?: components["parameters"]["Page"];
                pageSize?: components["parameters"]["PageSize"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description One page of incidents that match the filters. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentPage"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    exportIncidents: {
        parameters: {
            query?: {
                provider?: components["parameters"]["FilterProvider"];
                /** @description A lowercase branch, or `none` for incidents without branch. */
                branch?: components["parameters"]["FilterBranch"];
                status?: components["parameters"]["FilterStatus"];
                /** @description Which date the range applies to. */
                dateKind?: components["parameters"]["DateKind"];
                from?: components["parameters"]["DateFrom"];
                to?: components["parameters"]["DateTo"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The export file. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": string;
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    checkManualIncident: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentCore"];
            };
        };
        responses: {
            /** @description Whether the key is new, a duplicate or in conflict. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ManualCheckResult"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    createManualIncident: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentCore"];
            };
        };
        responses: {
            /** @description The incident was saved. */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Incident"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            /** @description The key already exists; nothing was created. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    getIncident: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The incident with its append-only history. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
        };
    };
    claimGlovoIncident: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClaimRequest"];
            };
        };
        responses: {
            /** @description The incident is now claimed. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Incident"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description The incident cannot be claimed manually. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    recordIncidentResult: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResultRequest"];
            };
        };
        responses: {
            /** @description The incident with its recorded result. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Incident"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description A result can only be recorded for a claimed incident. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    correctIncidentResult: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incidentId: components["parameters"]["IncidentId"];
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CorrectionRequest"];
            };
        };
        responses: {
            /** @description The incident with the correction in its history. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
            404: components["responses"]["NotFound"];
            /** @description Only a recorded result can be corrected. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Error"];
                };
            };
        };
    };
    getMetrics: {
        parameters: {
            query?: {
                /** @description Which date the range applies to. The default is the claim date. */
                dateKind?: "incident" | "claim" | "recovery";
                from?: components["parameters"]["DateFrom"];
                to?: components["parameters"]["DateTo"];
                provider?: components["parameters"]["FilterProvider"];
                /** @description A lowercase branch, or `none` for incidents without branch. */
                branch?: components["parameters"]["FilterBranch"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The figures for the environment and the chosen date. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Metrics"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    listBranchOptions: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The branches. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BranchList"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    getEmailQueue: {
        parameters: {
            query?: {
                state?: components["parameters"]["QueueState"];
                batchId?: components["parameters"]["QueueBatchId"];
                page?: components["parameters"]["Page"];
                pageSize?: components["parameters"]["PageSize"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The queue. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QueueView"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    pauseEmailQueue: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The queue is paused. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QueueStatus"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
    resumeEmailQueue: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description The queue is running. */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QueueStatus"];
                };
            };
            401: components["responses"]["Unauthenticated"];
            403: components["responses"]["Forbidden"];
        };
    };
}
