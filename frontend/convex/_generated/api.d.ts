/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as audit from "../audit.js";
import type * as cross_relations from "../cross_relations.js";
import type * as dashboards from "../dashboards.js";
import type * as datasets from "../datasets.js";
import type * as joins from "../joins.js";
import type * as lib_csv from "../lib/csv.js";
import type * as lib_export_templates from "../lib/export_templates.js";
import type * as lib_openrouter from "../lib/openrouter.js";
import type * as lib_prompts from "../lib/prompts.js";
import type * as ml from "../ml.js";
import type * as nlq from "../nlq.js";
import type * as pipeline_index from "../pipeline/index.js";
import type * as pipeline_stage1 from "../pipeline/stage1.js";
import type * as pipeline_stage2 from "../pipeline/stage2.js";
import type * as pipeline_stage3 from "../pipeline/stage3.js";
import type * as pipeline_stage4 from "../pipeline/stage4.js";
import type * as reports from "../reports.js";
import type * as scheduled_reports from "../scheduled_reports.js";
import type * as uploads from "../uploads.js";
import type * as users from "../users.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  audit: typeof audit;
  cross_relations: typeof cross_relations;
  dashboards: typeof dashboards;
  datasets: typeof datasets;
  joins: typeof joins;
  "lib/csv": typeof lib_csv;
  "lib/export_templates": typeof lib_export_templates;
  "lib/openrouter": typeof lib_openrouter;
  "lib/prompts": typeof lib_prompts;
  ml: typeof ml;
  nlq: typeof nlq;
  "pipeline/index": typeof pipeline_index;
  "pipeline/stage1": typeof pipeline_stage1;
  "pipeline/stage2": typeof pipeline_stage2;
  "pipeline/stage3": typeof pipeline_stage3;
  "pipeline/stage4": typeof pipeline_stage4;
  reports: typeof reports;
  scheduled_reports: typeof scheduled_reports;
  uploads: typeof uploads;
  users: typeof users;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
