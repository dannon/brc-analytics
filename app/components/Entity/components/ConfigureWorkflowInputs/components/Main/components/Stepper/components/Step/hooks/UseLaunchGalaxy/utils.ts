import {
  ANCHOR_TARGET,
  REL_ATTRIBUTE,
} from "@databiosphere/findable-ui/lib/components/Links/common/entities";
import { Workflow } from "../../../../../../../../../../../../apis/catalog/brc-analytics-catalog/common/entities";
import { WORKFLOW_PARAMETER_VARIABLE } from "../../../../../../../../../../../../apis/catalog/brc-analytics-catalog/common/schema-entities";
import { WorkflowRunCreateRequest } from "../../../../../../../../../../../../types/api";
import { DIFFERENTIAL_EXPRESSION_ANALYSIS } from "../../../../../../../../../../../../views/AnalyzeWorkflowsView/differentialExpressionAnalysis/constants";
import { LEXICMAP } from "../../../../../../../../../../../../views/AnalyzeWorkflowsView/lexicmap/constants";
import { LOGAN_SEARCH } from "../../../../../../../../../../../../views/AnalyzeWorkflowsView/loganSearch/constants";
import { ConfiguredInput } from "../../../../../../../../../../../../views/WorkflowInputsView/hooks/UseConfigureInputs/types";
import { ConfiguredValue } from "./types";

export function getRequiredParameterTypes(
  workflow: Workflow
): Record<WORKFLOW_PARAMETER_VARIABLE, boolean> {
  const result: Record<WORKFLOW_PARAMETER_VARIABLE, boolean> =
    Object.fromEntries(
      Object.values(WORKFLOW_PARAMETER_VARIABLE).map((variable) => [
        variable,
        workflow.parameters.some((param) => param.variable === variable),
      ])
    ) as Record<WORKFLOW_PARAMETER_VARIABLE, boolean>;

  return result;
}

/**
 * Validates and returns configured values for DE workflow.
 * @param configuredInput - Configured input.
 * @returns Configured values for DE workflow or undefined if invalid.
 */
function getDEConfiguredValues(
  configuredInput: ConfiguredInput
): ConfiguredValue | undefined {
  const {
    designFormula,
    geneModelUrl,
    primaryContrasts,
    referenceAssembly,
    sampleSheet,
    sampleSheetClassification,
    strandedness,
  } = configuredInput;

  // Validate required fields for DE workflow
  if (
    !referenceAssembly ||
    !geneModelUrl ||
    !sampleSheet?.length ||
    !sampleSheetClassification ||
    !designFormula
  ) {
    return;
  }

  return {
    designFormula,
    geneModelUrl,
    primaryContrasts: primaryContrasts ?? null,
    readRunsPaired: null,
    readRunsSingle: null,
    referenceAssembly,
    sampleSheet,
    sampleSheetClassification,
    strandedness,
    tracks: null,
  };
}

/**
 * Validates and returns configured values for SEQUENCE scope workflows.
 * SEQUENCE scope workflows (like LMLS) require sequence FASTA and numberOfHits from user input.
 * @param configuredInput - Configured input.
 * @returns Configured values for SEQUENCE workflow or undefined if invalid.
 */
function getLMLSConfiguredValues(
  configuredInput: ConfiguredInput
): ConfiguredValue | undefined {
  const { numberOfHits, sequence } = configuredInput;

  // Validate required fields for LMLS workflow
  if (!sequence || numberOfHits === undefined) {
    return;
  }

  return {
    designFormula: null,
    geneModelUrl: null,
    numberOfHits,
    primaryContrasts: null,
    readRunsPaired: null,
    readRunsSingle: null,
    referenceAssembly: "",
    sampleSheet: null,
    sampleSheetClassification: null,
    sequence,
    strandedness: undefined,
    tracks: null,
  };
}

/**
 * Validates and returns configured values for standard workflows.
 * @param configuredInput - Configured input.
 * @param workflow - Workflow to check required parameters.
 * @returns Configured values for standard workflow or undefined if invalid.
 */
function getStandardConfiguredValues(
  configuredInput: ConfiguredInput,
  workflow: Workflow
): ConfiguredValue | undefined {
  const { geneModelUrl, readRunsPaired, readRunsSingle, referenceAssembly } =
    configuredInput;

  // If workflow is not available yet, return undefined
  if (!workflow?.parameters) return;
  // Check which parameters are required by the workflow
  const requiredParams = getRequiredParameterTypes(workflow);

  // Only check for required values
  if (requiredParams.ASSEMBLY_FASTA_URL && !referenceAssembly) return;
  // For geneModelUrl, treat empty string as valid (user skipped or will upload manually)
  if (requiredParams.GENE_MODEL_URL && geneModelUrl === null) return;
  if (requiredParams.SANGER_READ_RUN_SINGLE && !readRunsSingle) return;
  if (requiredParams.SANGER_READ_RUN_PAIRED && !readRunsPaired) return;

  return {
    designFormula: null,
    geneModelUrl: geneModelUrl ?? null,
    primaryContrasts: null,
    readRunsPaired: readRunsPaired ?? null,
    readRunsSingle: readRunsSingle ?? null,
    // referenceAssembly is currently always set, but there are workflows that don't require referenceAssembly.
    // xref https://github.com/galaxyproject/brc-analytics/issues/652
    referenceAssembly: referenceAssembly!,
    sampleSheet: null,
    sampleSheetClassification: null,
    strandedness: undefined,
    tracks: configuredInput.tracks ?? null,
  };
}

/**
 * Returns the configured values from the configured input.
 * @param configuredInput - Configured input.
 * @param workflow - Workflow to check required parameters.
 * @returns Configured values.
 */
export function getConfiguredValues(
  configuredInput: ConfiguredInput,
  workflow: Workflow
): ConfiguredValue | undefined {
  // Handle Differential Expression Analysis workflow separately
  if (workflow.trsId === DIFFERENTIAL_EXPRESSION_ANALYSIS.trsId) {
    return getDEConfiguredValues(configuredInput);
  }

  // Handle LMLS workflows (SEQUENCE scope with no parameters)
  if (
    workflow.trsId === LOGAN_SEARCH.trsId ||
    workflow.trsId === LEXICMAP.trsId
  ) {
    return getLMLSConfiguredValues(configuredInput);
  }

  return getStandardConfiguredValues(configuredInput, workflow);
}

/**
 * Launches the Galaxy workflow.
 * Creates a hidden anchor element and clicks it to launch the workflow.
 * @param url - Galaxy URL.
 */
export function launchGalaxy(url: string): void {
  const el = document.createElement("a");
  el.href = url;
  el.rel = REL_ATTRIBUTE.NO_OPENER_NO_REFERRER;
  el.target = ANCHOR_TARGET.BLANK;
  document.body.appendChild(el);
  el.click();
  document.body.removeChild(el);
}

interface BuildWorkflowRunPayloadParams {
  assistantSessionId: string | null;
  configuredInput: ConfiguredInput;
  configuredValue: ConfiguredValue;
  handoffUrl: string;
  workflow: Workflow;
}

export function buildWorkflowRunPayload({
  assistantSessionId,
  configuredInput,
  configuredValue,
  handoffUrl,
  workflow,
}: BuildWorkflowRunPayloadParams): WorkflowRunCreateRequest {
  let galaxyInstanceUrl: string | null = null;

  try {
    galaxyInstanceUrl = new URL(handoffUrl).origin;
  } catch {
    galaxyInstanceUrl = null;
  }

  return {
    assembly_accession: configuredValue.referenceAssembly || null,
    assistant_session_id: assistantSessionId,
    galaxy_instance_url: galaxyInstanceUrl,
    handoff_url: handoffUrl,
    launch_source: assistantSessionId ? "assistant" : "site",
    parameters: {
      design_formula: configuredValue.designFormula ?? null,
      gene_model_url: configuredValue.geneModelUrl ?? null,
      number_of_hits: configuredValue.numberOfHits ?? null,
      primary_contrasts: configuredValue.primaryContrasts ?? null,
      read_runs_paired:
        configuredValue.readRunsPaired?.map(
          ({ runAccession }) => runAccession
        ) ?? [],
      read_runs_single:
        configuredValue.readRunsSingle?.map(
          ({ runAccession }) => runAccession
        ) ?? [],
      sample_sheet_classification:
        configuredValue.sampleSheetClassification ?? null,
      sample_sheet_rows: configuredValue.sampleSheet?.length ?? 0,
      sequence_file_name: configuredInput.sequenceFileName ?? null,
      sequence_length: configuredValue.sequence?.length ?? null,
      strandedness: configuredValue.strandedness ?? null,
      tracks:
        configuredValue.tracks?.map((track) => ({
          group_id: track.groupId,
          name: track.shortLabel ?? track.longLabel ?? track.bigDataUrl,
          url: track.bigDataUrl,
        })) ?? [],
    },
    workflow_id: workflow.workflowId ?? null,
    workflow_trs_id: workflow.trsId,
  };
}
