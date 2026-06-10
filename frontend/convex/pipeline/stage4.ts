import { getNumericColumns } from "../lib/csv";

export async function runStage4(
  ctx: any,
  args: {
    data: Record<string, any>[];
    relationships: any[];
    derivedColumns: any[];
  }
) {
  const { data, relationships, derivedColumns } = args;
  const numericCols = getNumericColumns(data);

  // Materialize derived columns
  const materializedColumns: any[] = [];

  for (const col of derivedColumns) {
    try {
      // Check if the formula references valid columns
      const formula = col.formula || "";
      const parts = formula.split(/[\s+\-*/()]+/);
      const refs = parts.filter((p: string) =>
        data[0] && p in data[0]
      );

      if (refs.length >= 1) {
        materializedColumns.push({
          name: col.name,
          dataType: col.dataType,
          description: col.description,
          expression: col.formula,
          confidence: col.confidence,
          status: "active",
        });
      }
    } catch (e) {
      console.warn(`Failed to materialize column ${col.name}:`, e);
    }
  }

  // Generate visualization schema
  const vizSchema = generateVizSchema(relationships);

  // Generate dashboard layout
  const dashboardLayout = generateDashboardLayout(relationships);

  return {
    derivedColumns: materializedColumns,
    vizSchema,
    dashboardLayout,
  };
}

function generateVizSchema(relationships: any[]): any {
  const charts = relationships.map((rel, idx) => ({
    id: `chart-${idx}`,
    type: rel.chartHint || "scatter",
    title: `${rel.sourceColumn} vs ${rel.targetColumn}`,
    encoding: {
      x: { field: rel.sourceColumn, type: "quantitative" },
      y: { field: rel.targetColumn, type: "quantitative" },
    },
    confidence: rel.confidence,
    description: rel.description,
    width: 400,
    height: 300,
  }));

  return {
    charts,
    theme: "light",
    interactivity: {
      zoom: true,
      pan: true,
      hoverTooltips: true,
    },
    config: {
      defaultWidth: 400,
      defaultHeight: 300,
      colorScheme: "tableau10",
    },
  };
}

function generateDashboardLayout(relationships: any[]): any {
  return {
    gridColumns: 2,
    responsiveBreakpoints: {
      mobile: { columns: 1, breakpointPx: 480 },
      tablet: { columns: 2, breakpointPx: 768 },
      desktop: { columns: 3, breakpointPx: 1024 },
    },
    chartPositions: relationships.map((_rel, idx) => ({
      id: `chart-${idx}`,
      priority: idx,
      width: 1,
      height: 1,
      x: idx % 2,
      y: Math.floor(idx / 2),
    })),
    filters: {
      global: true,
      linkedBrushing: true,
    },
    kpiSection: {
      enabled: true,
      position: "top",
      maxKpis: 4,
    },
  };
}
