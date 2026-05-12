# JSON UI component schemas

## text

Static or dynamic text display.

~~~json
{
  "additionalProperties": false,
  "description": "Displays text content. Can show static content, dynamic values from message parameters, values from UDF output, or results from DuckDB SQL queries. Priority: sql > udfValue > param > content.",
  "properties": {
    "content": {
      "default": "",
      "type": "string"
    },
    "param": {
      "description": "Parameter name to get value from message, higher priority than content",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders (e.g., SELECT COUNT(*) as count FROM {{my_udf}}). Returns first row's first column value. Highest priority.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    },
    "udfValue": {
      "description": "UDF query string (e.g., {{udf_name.column[0]}}) to get a single value",
      "type": "string"
    },
    "variant": {
      "default": "default",
      "description": "Text style variant",
      "enum": [
        "default",
        "muted",
        "small",
        "large",
        "h1",
        "h2",
        "h3",
        "h4"
      ],
      "type": "string"
    }
  },
  "required": [
    "content",
    "variant"
  ],
  "type": "object"
}
~~~
## input

Text input with optional param sync.

~~~json
{
  "additionalProperties": false,
  "description": "An input field that can optionally sync with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular input.",
  "properties": {
    "defaultValue": {
      "default": "",
      "type": "string"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "label": {
      "description": "Label text displayed above the input",
      "type": "string"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular input.",
      "type": "string"
    },
    "placeholder": {
      "default": "Enter value...",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    },
    "type": {
      "default": "text",
      "type": "string"
    }
  },
  "required": [
    "placeholder",
    "defaultValue",
    "disabled",
    "type"
  ],
  "type": "object"
}
~~~
## button

Clickable button with optional param broadcast.

~~~json
{
  "additionalProperties": false,
  "description": "A clickable button for triggering actions. If param is provided, broadcasts click count to that canvas parameter.",
  "properties": {
    "centered": {
      "default": false,
      "description": "If true, centers the button within the node.",
      "type": "boolean"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "label": {
      "default": "Button",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter name to sync click count with. Each click increments the count.",
      "type": "string"
    },
    "size": {
      "default": "default",
      "enum": [
        "default",
        "sm",
        "lg"
      ],
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    },
    "variant": {
      "default": "default",
      "enum": [
        "default",
        "destructive",
        "outline",
        "secondary",
        "ghost",
        "link"
      ],
      "type": "string"
    }
  },
  "required": [
    "label",
    "variant",
    "size",
    "disabled",
    "centered"
  ],
  "type": "object"
}
~~~
## dropdown

Select dropdown with SQL or static options.

~~~json
{
  "additionalProperties": false,
  "description": "A dropdown that syncs with canvas parameters. Prefer sql (DuckDB query with {{udf_name}} placeholders returning 'value' and 'label' columns) for dynamic options from UDF DataFrames. Fall back to options array for static choices.",
  "properties": {
    "centered": {
      "default": false,
      "description": "If true, centers the dropdown within the node.",
      "type": "boolean"
    },
    "defaultValue": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "additionalProperties": {},
          "type": "object"
        }
      ],
      "default": "",
      "description": "Initial value when no canvas/form value exists. Can be a constant string, UDF query (e.g., {{my_udf.default_city[0]}}), or a JSON object matching an option value."
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "label": {
      "description": "Label text displayed above the dropdown",
      "type": "string"
    },
    "options": {
      "description": "Static array of options. Used when sql is not provided or when sql fails. Each option must have non-empty value and label.",
      "items": {
        "additionalProperties": false,
        "description": "A single dropdown option with value (string or object) and label (displayed). String options with empty value are filtered out.",
        "properties": {
          "label": {
            "type": "string"
          },
          "value": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "additionalProperties": {},
                "type": "object"
              }
            ]
          }
        },
        "required": [
          "value"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular dropdown.",
      "type": "string"
    },
    "placeholder": {
      "default": "Select an option...",
      "description": "Placeholder text shown when nothing is selected",
      "type": "string"
    },
    "searchable": {
      "default": false,
      "description": "If true, shows a search input inside the dropdown panel.",
      "type": "boolean"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'value' and 'label' columns. Takes precedence over options. Requires at least one {{udf_name}} placeholder.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "required": [
    "placeholder",
    "defaultValue",
    "disabled",
    "centered",
    "searchable"
  ],
  "type": "object"
}
~~~
## bar-chart

Bar chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A bar chart powered by DuckDB SQL queries against UDF outputs. Query must return 'label' and 'value' columns. Uses {{udf_name}} placeholders to reference UDF DataFrames.",
  "properties": {
    "animationMs": {
      "default": 300,
      "description": "Bar animation duration in milliseconds. 0 disables animation. Default 300ms, and animation only runs when data changes.",
      "type": "number"
    },
    "barColor": {
      "default": "#E8FF59",
      "description": "Bar fill color. Default is Fused lime yellow (#E8FF59).",
      "type": "string"
    },
    "barOpacity": {
      "default": 1,
      "description": "Bar fill opacity from 0 (transparent) to 1 (solid).",
      "type": "number"
    },
    "barRadius": {
      "default": 4,
      "description": "Corner radius of bars in pixels. 0 for sharp corners.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force the value axis to start at 0.",
      "type": "boolean"
    },
    "bottomMargin": {
      "description": "Bottom margin in pixels. Overrides the auto-calculated value from rotateLabels. Useful when labels are clipped.",
      "type": "number"
    },
    "horizontal": {
      "default": false,
      "description": "If true, renders horizontal bars (categories on y-axis, values on x-axis). Good for ranked lists.",
      "type": "boolean"
    },
    "hoverColor": {
      "description": "Bar fill color on hover. If omitted, no hover highlight is shown.",
      "type": "string"
    },
    "limit": {
      "description": "Maximum number of bars to show. Applied after sorting. Omit for no limit.",
      "type": "number"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels -45 degrees. Useful for long category names.",
      "type": "boolean"
    },
    "showGrid": {
      "default": false,
      "description": "Show subtle horizontal grid lines behind bars.",
      "type": "boolean"
    },
    "showValues": {
      "default": false,
      "description": "Show the numeric value label on each bar.",
      "type": "boolean"
    },
    "sort": {
      "default": "none",
      "description": "Sort bars by value. \"desc\" for highest first, \"asc\" for lowest first, \"none\" for SQL order.",
      "enum": [
        "asc",
        "desc",
        "none"
      ],
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; background-color: #1a1a1a\")",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "Font size for x-axis labels in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Font size for y-axis labels in pixels.",
      "type": "number"
    }
  },
  "required": [
    "sql",
    "barColor",
    "barOpacity",
    "barRadius",
    "showGrid",
    "rotateLabels",
    "horizontal",
    "showValues",
    "sort",
    "xAxisFontSize",
    "yAxisFontSize",
    "beginAtZero",
    "animationMs"
  ],
  "type": "object"
}
~~~
## line-chart

Line/area chart for time series driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A line/area chart for time series data, powered by DuckDB SQL queries. Query must return 'label' and 'value' columns. Add a 'series' column for multiple lines.",
  "properties": {
    "activeDotSize": {
      "default": 5,
      "description": "Radius of the active (hovered) data point dot in pixels.",
      "type": "number"
    },
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "areaOpacity": {
      "default": 0.2,
      "description": "Opacity of the area fill (0-1). Only used when showArea is true.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force the y-axis to start at 0. Ignored if yMin is set.",
      "type": "boolean"
    },
    "bottomMargin": {
      "description": "Bottom margin in pixels. Overrides the auto-calculated value from rotateLabels. Useful when labels are clipped.",
      "type": "number"
    },
    "curveType": {
      "default": "smooth",
      "description": "Interpolation curve: \"linear\" for straight segments, \"smooth\" for bezier curves, \"step\" for stepped lines.",
      "enum": [
        "linear",
        "smooth",
        "step"
      ],
      "type": "string"
    },
    "dotSize": {
      "default": 3,
      "description": "Radius of data point dots in pixels.",
      "type": "number"
    },
    "limit": {
      "description": "Maximum number of data points to show. Applied after sorting. Omit for no limit.",
      "type": "number"
    },
    "lineColor": {
      "default": "#E8FF59",
      "description": "Line color for single-series charts. Ignored when multiple series are present (auto-palette is used). Default is Fused lime yellow (#E8FF59).",
      "type": "string"
    },
    "lineOpacity": {
      "default": 1,
      "description": "Line stroke opacity from 0 (transparent) to 1 (solid).",
      "type": "number"
    },
    "lineWidth": {
      "default": 2,
      "description": "Line stroke width in pixels.",
      "type": "number"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels -45 degrees. Useful for long date strings.",
      "type": "boolean"
    },
    "showArea": {
      "default": true,
      "description": "Fill the area under the line with a gradient.",
      "type": "boolean"
    },
    "showDots": {
      "default": false,
      "description": "Show data point dots on the line.",
      "type": "boolean"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind the chart.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for multi-series charts. Auto-hidden when there is only one series.",
      "type": "boolean"
    },
    "sort": {
      "default": "none",
      "description": "Sort data points by value. \"desc\" for highest first, \"asc\" for lowest first, \"none\" for SQL order.",
      "enum": [
        "asc",
        "desc",
        "none"
      ],
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns. Optional 'series' column for multi-line charts.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px; background-color: #1a1a1a\")",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "Font size for x-axis labels in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Font size for y-axis labels in pixels.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum value for the y-axis.",
      "type": "number"
    },
    "yMin": {
      "description": "Fixed minimum value for the y-axis. Overrides beginAtZero.",
      "type": "number"
    }
  },
  "required": [
    "sql",
    "lineColor",
    "lineWidth",
    "lineOpacity",
    "showDots",
    "dotSize",
    "activeDotSize",
    "showArea",
    "areaOpacity",
    "curveType",
    "showGrid",
    "showLegend",
    "rotateLabels",
    "xAxisFontSize",
    "yAxisFontSize",
    "beginAtZero",
    "animationMs",
    "sort"
  ],
  "type": "object"
}
~~~
## stacked-bar-chart

Stacked bar chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A stacked bar chart powered by DuckDB SQL. Query should return label, series, and value.",
  "properties": {
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force value axis to start at 0.",
      "type": "boolean"
    },
    "bottomMargin": {
      "description": "Override bottom margin in pixels.",
      "type": "number"
    },
    "horizontal": {
      "default": false,
      "description": "Render horizontal stacked bars.",
      "type": "boolean"
    },
    "limit": {
      "description": "Maximum number of categories to show after sorting.",
      "type": "number"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels by -45 degrees.",
      "type": "boolean"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind bars.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for stacked series.",
      "type": "boolean"
    },
    "sort": {
      "default": "none",
      "description": "Sort categories by total stacked value. 'none' keeps SQL order.",
      "enum": [
        "asc",
        "desc",
        "none"
      ],
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label', 'series', and 'value' columns.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    }
  },
  "required": [
    "sql",
    "horizontal",
    "showGrid",
    "showLegend",
    "rotateLabels",
    "xAxisFontSize",
    "yAxisFontSize",
    "beginAtZero",
    "sort",
    "animationMs"
  ],
  "type": "object"
}
~~~
## stacked-area-chart

Stacked area chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A stacked area chart powered by DuckDB SQL. Query should return label, series, and value.",
  "properties": {
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "areaOpacity": {
      "default": 0.6,
      "description": "Opacity of each stacked area from 0 to 1.",
      "type": "number"
    },
    "beginAtZero": {
      "default": true,
      "description": "Force y-axis to start at zero.",
      "type": "boolean"
    },
    "bottomMargin": {
      "description": "Override bottom margin in pixels.",
      "type": "number"
    },
    "brushHeight": {
      "default": 30,
      "description": "Height of brush slider in pixels.",
      "type": "number"
    },
    "curveType": {
      "default": "smooth",
      "description": "Interpolation curve type.",
      "enum": [
        "linear",
        "smooth",
        "step"
      ],
      "type": "string"
    },
    "limit": {
      "description": "Maximum number of x-axis points to show.",
      "type": "number"
    },
    "rotateLabels": {
      "default": true,
      "description": "Rotate x-axis labels by -45 degrees.",
      "type": "boolean"
    },
    "showBrush": {
      "default": true,
      "description": "Show brush slider for range selection.",
      "type": "boolean"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind the chart.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend for stacked series.",
      "type": "boolean"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label', 'series', and 'value' columns.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum y-axis value.",
      "type": "number"
    },
    "yMin": {
      "description": "Fixed minimum y-axis value.",
      "type": "number"
    }
  },
  "required": [
    "sql",
    "areaOpacity",
    "curveType",
    "showGrid",
    "showLegend",
    "showBrush",
    "brushHeight",
    "rotateLabels",
    "xAxisFontSize",
    "yAxisFontSize",
    "beginAtZero",
    "animationMs"
  ],
  "type": "object"
}
~~~
## scatter-chart

Scatter chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A scatter chart powered by DuckDB SQL. Query must return x and y numeric columns.",
  "properties": {
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "defaultPointSize": {
      "default": 70,
      "description": "Default point size when SQL does not return a size column.",
      "type": "number"
    },
    "maxBubbleSize": {
      "default": 160,
      "description": "Maximum rendered bubble size when using a size column.",
      "type": "number"
    },
    "minBubbleSize": {
      "default": 10,
      "description": "Minimum rendered bubble size when using a size column.",
      "type": "number"
    },
    "pointColor": {
      "default": "#E8FF59",
      "description": "Point color for single-series charts.",
      "type": "string"
    },
    "pointOpacity": {
      "default": 0.85,
      "description": "Point opacity from 0 to 1.",
      "type": "number"
    },
    "pointStrokeColor": {
      "default": "#111827",
      "description": "Outline color for points.",
      "type": "string"
    },
    "pointStrokeWidth": {
      "default": 0.5,
      "description": "Outline width of points in pixels.",
      "type": "number"
    },
    "showGrid": {
      "default": true,
      "description": "Show subtle grid lines behind points.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show legend when multiple series are present.",
      "type": "boolean"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'x' and 'y'. Optional: 'series', 'size', 'label'.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xAxisFontSize": {
      "default": 11,
      "description": "X-axis label font size in pixels.",
      "type": "number"
    },
    "xMax": {
      "description": "Fixed maximum value for x-axis.",
      "type": "number"
    },
    "xMin": {
      "description": "Fixed minimum value for x-axis.",
      "type": "number"
    },
    "yAxisFontSize": {
      "default": 11,
      "description": "Y-axis label font size in pixels.",
      "type": "number"
    },
    "yMax": {
      "description": "Fixed maximum value for y-axis.",
      "type": "number"
    },
    "yMin": {
      "description": "Fixed minimum value for y-axis.",
      "type": "number"
    }
  },
  "required": [
    "sql",
    "pointColor",
    "pointOpacity",
    "defaultPointSize",
    "pointStrokeWidth",
    "pointStrokeColor",
    "minBubbleSize",
    "maxBubbleSize",
    "showGrid",
    "showLegend",
    "xAxisFontSize",
    "yAxisFontSize",
    "animationMs"
  ],
  "type": "object"
}
~~~
## donut-chart

Donut chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A donut chart powered by DuckDB SQL. Query must return label and value columns.",
  "properties": {
    "animationMs": {
      "default": 300,
      "description": "Animation duration in milliseconds. 0 disables animation. Animation only plays on data changes, not on zoom/resize.",
      "type": "number"
    },
    "innerRadius": {
      "default": 56,
      "description": "Inner radius in pixels (donut hole size).",
      "type": "number"
    },
    "limit": {
      "description": "Maximum number of slices to show after sorting.",
      "type": "number"
    },
    "outerRadius": {
      "default": 88,
      "description": "Outer radius in pixels.",
      "type": "number"
    },
    "showCenterTotal": {
      "default": true,
      "description": "Show total value text in donut center.",
      "type": "boolean"
    },
    "showLabels": {
      "default": false,
      "description": "Show percentage labels on slices.",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show category legend.",
      "type": "boolean"
    },
    "sort": {
      "default": "none",
      "description": "Sort slices by value.",
      "enum": [
        "asc",
        "desc",
        "none"
      ],
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'label' and 'value' columns.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    }
  },
  "required": [
    "sql",
    "innerRadius",
    "outerRadius",
    "showLegend",
    "showLabels",
    "showCenterTotal",
    "sort",
    "animationMs"
  ],
  "type": "object"
}
~~~
## heatmap-chart

Heatmap chart driven by DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "A matrix heatmap powered by DuckDB SQL. Query must return x, y, and value columns.",
  "properties": {
    "cellGap": {
      "default": 4,
      "description": "Gap between heatmap cells in pixels.",
      "type": "number"
    },
    "highColor": {
      "default": "#E8FF59",
      "description": "Color for the maximum value.",
      "type": "string"
    },
    "lowColor": {
      "default": "#111827",
      "description": "Color for the minimum value.",
      "type": "string"
    },
    "minCellHeight": {
      "default": 28,
      "description": "Minimum cell height in pixels.",
      "type": "number"
    },
    "showValues": {
      "default": false,
      "description": "Show numeric values inside each cell.",
      "type": "boolean"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Must return 'x', 'y', and 'value' columns.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string.",
      "type": "string"
    },
    "title": {
      "description": "Chart title displayed above",
      "type": "string"
    },
    "xLabel": {
      "description": "Optional x-axis title.",
      "type": "string"
    },
    "yLabel": {
      "description": "Optional y-axis title.",
      "type": "string"
    }
  },
  "required": [
    "sql",
    "showValues",
    "cellGap",
    "minCellHeight",
    "lowColor",
    "highColor"
  ],
  "type": "object"
}
~~~
## big-number

Dashboard big-number card with formatted value.

~~~json
{
  "additionalProperties": false,
  "description": "Big number card for dashboards. Shows a single large formatted value from SQL, UDF, param, or static content.",
  "properties": {
    "color": {
      "type": "string"
    },
    "content": {
      "default": "",
      "type": "string"
    },
    "decimals": {
      "default": 1,
      "type": "number"
    },
    "format": {
      "default": "compact",
      "description": "How to format the number. \"compact\" abbreviates large values (e.g. 1.2M, 45.3K, 2.5B). \"comma\" adds thousand separators (e.g. 1,234,567). \"none\" displays the raw value as-is.",
      "enum": [
        "compact",
        "comma",
        "none"
      ],
      "type": "string"
    },
    "label": {
      "type": "string"
    },
    "param": {
      "type": "string"
    },
    "prefix": {
      "default": "",
      "type": "string"
    },
    "size": {
      "default": 36,
      "description": "Font size of the number in pixels. e.g. 24, 36, 48, 72, 96, 144. Default 36.",
      "type": "number"
    },
    "sql": {
      "description": "DuckDB SQL with {{udf_name}} and $param_name placeholders. Returns first column of first row.",
      "type": "string"
    },
    "style": {
      "type": "string"
    },
    "suffix": {
      "default": "",
      "type": "string"
    }
  },
  "required": [
    "content",
    "prefix",
    "suffix",
    "format",
    "decimals",
    "size"
  ],
  "type": "object"
}
~~~
## code-editor

Code editor with syntax highlighting.

~~~json
{
  "additionalProperties": false,
  "description": "Code editor with multi-language syntax highlighting. Syncs content with a canvas parameter.",
  "properties": {
    "debounceMs": {
      "default": 0,
      "type": "number"
    },
    "defaultValue": {
      "default": "",
      "description": "Initial content",
      "type": "string"
    },
    "label": {
      "description": "Label displayed above the editor",
      "type": "string"
    },
    "language": {
      "default": "sql",
      "description": "Syntax highlighting language.",
      "enum": [
        "sql",
        "python",
        "javascript",
        "json",
        "markdown"
      ],
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter name to sync the editor content with",
      "type": "string"
    },
    "placeholderText": {
      "default": "Enter code...",
      "type": "string"
    },
    "readOnly": {
      "default": false,
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles (e.g. \"padding: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "defaultValue",
    "language",
    "placeholderText",
    "readOnly",
    "debounceMs"
  ],
  "type": "object"
}
~~~
## sql-table

Table rendered from a DuckDB SQL query.

~~~json
{
  "additionalProperties": false,
  "description": "Renders the results of a DuckDB SQL query in a table similar to the UDF node Data Table. Supports {{udf_name}} placeholders and $param_name canvas parameters. Optional AI chat can author the SQL for you.",
  "properties": {
    "aiBuilderMode": {
      "default": "disabled",
      "description": "Whether the AI chat is active. 'enabled' shows the AI chat panel; 'disabled' hides it entirely. AI actions require authentication.",
      "enum": [
        "enabled",
        "disabled"
      ],
      "type": "string"
    },
    "aiPanel": {
      "default": "right",
      "description": "Side the AI chat panel is docked on when aiBuilderMode is 'enabled'.",
      "enum": [
        "left",
        "right"
      ],
      "type": "string"
    },
    "editorCollapsed": {
      "default": true,
      "description": "Whether the editor panel starts collapsed.",
      "type": "boolean"
    },
    "editorHeight": {
      "description": "Optional initial editor height in pixels. If omitted, height auto-fits the current content.",
      "type": "number"
    },
    "filterable": {
      "default": false,
      "description": "Show filter inputs below column headers",
      "type": "boolean"
    },
    "showEditor": {
      "default": false,
      "description": "Show a collapsible editor panel below the component for inspecting and editing the current value.",
      "type": "boolean"
    },
    "sortable": {
      "default": true,
      "description": "Allow sorting rows by clicking column headers",
      "type": "boolean"
    },
    "sql": {
      "description": "DuckDB SQL query with {{udf_name}} and $param_name placeholders. Example: SELECT * FROM {{my_udf}} LIMIT 100",
      "type": "string"
    },
    "title": {
      "description": "Table title displayed above",
      "type": "string"
    }
  },
  "required": [
    "sql",
    "sortable",
    "filterable",
    "aiBuilderMode",
    "aiPanel",
    "showEditor",
    "editorCollapsed"
  ],
  "type": "object"
}
~~~
## form

Form container that submits child values together.
- Has children: yes

~~~json
{
  "additionalProperties": false,
  "description": "A form container that collects child input/dropdown values and submits on button click. If form 'param' is provided, all child values are broadcast as one object to that parameter. If omitted, each child field parameter is broadcast individually. Children should use 'param' prop to register with the form. It only supports input, dropdown and text components.",
  "properties": {
    "card": {
      "default": true,
      "description": "If true, wraps the form in a card-like container.",
      "type": "boolean"
    },
    "centered": {
      "default": false,
      "description": "If true, centers the form container within the node.",
      "type": "boolean"
    },
    "description": {
      "type": "string"
    },
    "param": {
      "description": "Optional canvas parameter name to broadcast consolidated form data to. If omitted, each child field is broadcast individually on submit.",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 16px; background-color: #f0f0f0\")",
      "type": "string"
    },
    "submitLabel": {
      "default": "Submit",
      "type": "string"
    },
    "submitPosition": {
      "default": "bottom",
      "description": "Position of the submit button",
      "enum": [
        "bottom",
        "top"
      ],
      "type": "string"
    },
    "title": {
      "type": "string"
    }
  },
  "required": [
    "submitLabel",
    "submitPosition",
    "card",
    "centered"
  ],
  "type": "object"
}
~~~
## fused-map

Interactive map with tile and vector layers.

~~~json
{
  "additionalProperties": false,
  "description": "Interactive map with Mapbox GL (mvt, raster, geojson) and deck.gl (h3, heatmap, arc, scatterplot) layers.",
  "properties": {
    "autoSend": {
      "default": false,
      "description": "Automatically send bounds on pan/zoom",
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 600,
      "description": "Debounce ms for auto-send (0 = send on every move)",
      "type": "number"
    },
    "basemap": {
      "default": "mapbox://styles/mapbox/dark-v11",
      "description": "Mapbox style URL",
      "type": "string"
    },
    "centerLat": {
      "default": 39.5,
      "type": "number"
    },
    "centerLng": {
      "default": -98,
      "type": "number"
    },
    "layers": {
      "default": [],
      "items": {
        "additionalProperties": false,
        "properties": {
          "data": {
            "description": "Inline GeoJSON FeatureCollection (geojson type)"
          },
          "geometryColumn": {
            "description": "Column containing GeoJSON geometry strings (use ST_AsGeoJSON in SQL). Defaults to 'geometry'.",
            "type": "string"
          },
          "h3Column": {
            "description": "Column containing H3 hex indexes (for h3 layer type).",
            "type": "string"
          },
          "id": {
            "description": "Unique layer identifier",
            "type": "string"
          },
          "latColumn": {
            "description": "Column for latitude (point data). Defaults to 'lat'.",
            "type": "string"
          },
          "legend": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "title": {
                    "type": "string"
                  }
                },
                "type": "object"
              }
            ],
            "description": "Show color legend for this layer. true = auto title, {title} = custom title. Only applies when fillColor or lineColor is data-driven."
          },
          "lngColumn": {
            "description": "Column for longitude (point data). Defaults to 'lng'.",
            "type": "string"
          },
          "maxRequests": {
            "description": "Maximum parallel tile requests for tiled layers",
            "type": "number"
          },
          "maxZoom": {
            "description": "Maximum zoom for tiled layers (mvt, raster, tiled h3)",
            "type": "number"
          },
          "minZoom": {
            "description": "Minimum zoom for tiled layers (mvt, raster, tiled h3)",
            "type": "number"
          },
          "name": {
            "description": "Display name for the layer",
            "type": "string"
          },
          "sourceLayer": {
            "description": "Source layer name for MVT tiles (defaults to 'default')",
            "type": "string"
          },
          "sql": {
            "description": "DuckDB SQL query with {{udf_name}} placeholders. Rows are converted to GeoJSON for rendering.",
            "type": "string"
          },
          "style": {
            "additionalProperties": false,
            "properties": {
              "coverage": {
                "description": "H3 hex coverage 0-1 (1 = no gap, 0.8 = small gaps)",
                "maximum": 1,
                "minimum": 0,
                "type": "number"
              },
              "elevationAttr": {
                "description": "Feature property to use for extrusion height",
                "type": "string"
              },
              "elevationScale": {
                "description": "Multiplier for extrusion height values",
                "type": "number"
              },
              "extruded": {
                "description": "Enable 3D extrusion (h3, deck-geojson)",
                "type": "boolean"
              },
              "fillColor": {
                "description": "Fill color: [r,g,b], CSS string, or data-driven {type:\"continuous\"|\"categorical\", attr, ...}"
              },
              "lineColor": {
                "description": "Stroke color: [r,g,b], CSS string, or data-driven {type:\"continuous\"|\"categorical\", attr, ...}"
              },
              "lineWidth": {
                "description": "Stroke width in pixels",
                "type": "number"
              },
              "opacity": {
                "description": "Layer opacity 0-1",
                "maximum": 1,
                "minimum": 0,
                "type": "number"
              },
              "pointRadius": {
                "description": "Circle radius for point features",
                "type": "number"
              }
            },
            "type": "object"
          },
          "tileUrl": {
            "description": "Tile URL template with {x}/{y}/{z} placeholders (mvt, raster, tiled h3)",
            "type": "string"
          },
          "tooltip": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              }
            ],
            "description": "Show tooltip on hover. true = all properties, string[] = specific properties."
          },
          "type": {
            "description": "Layer type: mvt/raster/geojson (Mapbox native), h3/heatmap/arc/scatterplot/deck-geojson (deck.gl)",
            "enum": [
              "mvt",
              "raster",
              "geojson",
              "h3",
              "heatmap",
              "arc",
              "scatterplot",
              "deck-geojson"
            ],
            "type": "string"
          },
          "visible": {
            "default": true,
            "type": "boolean"
          },
          "zoomOffset": {
            "description": "Zoom offset for tiled layers (useful for hex tile generalization)",
            "type": "number"
          }
        },
        "required": [
          "id",
          "type",
          "visible"
        ],
        "type": "object"
      },
      "type": "array"
    },
    "maxZoom": {
      "description": "Maximum zoom level (0-24)",
      "type": "number"
    },
    "minZoom": {
      "description": "Minimum zoom level (0-24)",
      "type": "number"
    },
    "param": {
      "description": "Canvas parameter name to sync viewport bounds [west, south, east, north]",
      "type": "string"
    },
    "showBasemapSwitcher": {
      "default": true,
      "description": "Show dark/light/satellite basemap toggle",
      "type": "boolean"
    },
    "showControls": {
      "default": true,
      "description": "Show zoom navigation controls",
      "type": "boolean"
    },
    "showLayerPanel": {
      "default": true,
      "description": "Show layer controls panel for toggling visibility and opacity",
      "type": "boolean"
    },
    "showLegend": {
      "default": true,
      "description": "Show color legend for layers with data-driven colors",
      "type": "boolean"
    },
    "showScale": {
      "default": true,
      "description": "Show scale bar",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string",
      "type": "string"
    },
    "zoom": {
      "default": 4,
      "type": "number"
    }
  },
  "required": [
    "basemap",
    "centerLng",
    "centerLat",
    "zoom",
    "layers",
    "showControls",
    "showScale",
    "showBasemapSwitcher",
    "showLegend",
    "showLayerPanel",
    "autoSend",
    "autoSendDebounceMs"
  ],
  "type": "object"
}
~~~
## map-bounds

Map that syncs viewport bounds to param.

~~~json
{
  "additionalProperties": false,
  "description": "Interactive Mapbox map that syncs viewport bounds [west, south, east, north] with a canvas parameter. Supports auto-send on pan/zoom or manual send via button.",
  "properties": {
    "autoSend": {
      "default": false,
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 600,
      "type": "number"
    },
    "buttonLabel": {
      "default": "Send View",
      "type": "string"
    },
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter for bounds [west, south, east, north]",
      "type": "string"
    },
    "showSearch": {
      "default": false,
      "description": "Show a geocoder search bar overlay on the map.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px; overflow: hidden\")",
      "type": "string"
    },
    "styleUrl": {
      "default": "mapbox://styles/mapbox/dark-v10",
      "type": "string"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    }
  },
  "required": [
    "centerLng",
    "centerLat",
    "zoom",
    "styleUrl",
    "buttonLabel",
    "autoSend",
    "autoSendDebounceMs",
    "showSearch"
  ],
  "type": "object"
}
~~~
## map-h3

Map that emits H3 cell at center.

~~~json
{
  "additionalProperties": false,
  "description": "Interactive map that emits the H3 hex cell at the map center. Resolution can be fixed or auto-derived from zoom.",
  "properties": {
    "autoSend": {
      "default": false,
      "type": "boolean"
    },
    "autoSendDebounceMs": {
      "default": 300,
      "type": "number"
    },
    "boundsParam": {
      "description": "Canvas parameter name to emit the viewport bounds as \"west,south,east,north\".",
      "type": "string"
    },
    "buttonLabel": {
      "default": "Send H3 cell",
      "type": "string"
    },
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "h3Res": {
      "description": "Fixed H3 resolution (0-15). If omitted, resolution is auto-derived from the map zoom level.",
      "maximum": 15,
      "minimum": 0,
      "type": "integer"
    },
    "hexColor": {
      "default": "#E8FF59",
      "description": "Hex outline & fill color.",
      "type": "string"
    },
    "hexOpacity": {
      "default": 0.03,
      "description": "Hex fill opacity. 0 = transparent, 1 = solid. Default 0.03 for a very slight fill.",
      "maximum": 1,
      "minimum": 0,
      "type": "number"
    },
    "kRing": {
      "default": 0,
      "description": "K-ring radius around the center hex. 0 = center only. 1-6 = include surrounding rings.",
      "maximum": 6,
      "minimum": 0,
      "type": "integer"
    },
    "kRingParam": {
      "description": "Canvas parameter name to emit a JSON array of all hex IDs in the k-ring (includes center).",
      "type": "string"
    },
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "latParam": {
      "description": "Canvas parameter name to emit the center latitude.",
      "type": "string"
    },
    "lngParam": {
      "description": "Canvas parameter name to emit the center longitude.",
      "type": "string"
    },
    "maxZoom": {
      "description": "Maximum zoom level. If omitted and h3Res is set, defaults to the zoom ceiling for that resolution so the user cannot zoom past the hex size.",
      "type": "number"
    },
    "minZoom": {
      "description": "Minimum zoom level. Prevents zooming out beyond this level.",
      "type": "number"
    },
    "param": {
      "description": "Canvas parameter for the H3 cell string",
      "type": "string"
    },
    "paramType": {
      "default": "string",
      "description": "Emit the H3 cell as a hex string (\"string\") or as a BigInt number (\"int\").",
      "enum": [
        "string",
        "int"
      ],
      "type": "string"
    },
    "resOffset": {
      "default": 0,
      "description": "Offset added to the auto-derived resolution. Positive = smaller hexes, negative = bigger hexes.",
      "maximum": 9007199254740991,
      "minimum": -9007199254740991,
      "type": "integer"
    },
    "resParam": {
      "description": "Canvas parameter name to emit the current H3 resolution.",
      "type": "string"
    },
    "sendOnMove": {
      "default": false,
      "description": "When true and autoSend is true, emit when the hex changes while dragging/zooming (debounce defaults to 0). When false, emit only when movement ends.",
      "type": "boolean"
    },
    "showBasemapSwitcher": {
      "default": true,
      "description": "Show Dark / Light / Satellite basemap toggle on the map.",
      "type": "boolean"
    },
    "showDetails": {
      "default": true,
      "description": "Show hex ID and resolution overlay on the map.",
      "type": "boolean"
    },
    "showSearch": {
      "default": false,
      "description": "Show a geocoder search bar overlay on the map.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string",
      "type": "string"
    },
    "styleUrl": {
      "default": "mapbox://styles/mapbox/dark-v11",
      "type": "string"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    },
    "zoomParam": {
      "description": "Canvas parameter name to emit the current zoom level.",
      "type": "string"
    }
  },
  "required": [
    "paramType",
    "centerLng",
    "centerLat",
    "zoom",
    "resOffset",
    "hexColor",
    "hexOpacity",
    "showDetails",
    "styleUrl",
    "showBasemapSwitcher",
    "buttonLabel",
    "autoSend",
    "autoSendDebounceMs",
    "sendOnMove",
    "kRing",
    "showSearch"
  ],
  "type": "object"
}
~~~
## widget-builder

Builds and renders a widget from a param-supplied or inline definition object.

~~~json
{
  "additionalProperties": false,
  "description": "Renders a widget definition received via a canvas param or inline. Use \"$param_name\" to render whatever a dropdown (or other sender) broadcasts. Set showEditor to enable a live JSON editor panel.",
  "properties": {
    "aiBuilderMode": {
      "default": "disabled",
      "description": "Whether the AI widget builder is active. 'enabled' shows the AI panel; 'disabled' hides it entirely. AI actions require authentication.",
      "enum": [
        "enabled",
        "disabled"
      ],
      "type": "string"
    },
    "aiPanel": {
      "default": "bottom",
      "description": "Position of the AI panel when aiBuilderMode is 'enabled'. 'top'/'bottom' show a compact input bar above/below the widget. 'left'/'right' show a full chat panel as a side column.",
      "enum": [
        "top",
        "bottom",
        "left",
        "right"
      ],
      "type": "string"
    },
    "allowedWidgetTypes": {
      "default": "all",
      "description": "Comma-separated list of widget types that may be rendered (e.g. \"div,text,input\"). Use \"all\" to allow every type.",
      "type": "string"
    },
    "defaultValue": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "additionalProperties": {},
          "type": "object"
        }
      ],
      "description": "Widget definition to render. Use \"$param_name\" to read from a canvas param, or provide a literal { type, props } object."
    },
    "editorCollapsed": {
      "default": true,
      "description": "Whether the editor panel starts collapsed.",
      "type": "boolean"
    },
    "editorHeight": {
      "description": "Optional initial height in pixels. If omitted, height auto-fits JSON line count.",
      "type": "number"
    },
    "initialPrompt": {
      "description": "When set and aiBuilderMode is 'enabled', this prompt is automatically submitted to the AI on first load.",
      "type": "string"
    },
    "showEditor": {
      "default": false,
      "description": "Show a collapsible JSON editor panel for inspecting/editing the widget definition.",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"padding: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "defaultValue",
    "showEditor",
    "editorCollapsed",
    "aiBuilderMode",
    "aiPanel",
    "allowedWidgetTypes"
  ],
  "type": "object"
}
~~~
## sql-runner

Named SQL source for descendant components.
- Has children: yes

~~~json
{
  "additionalProperties": false,
  "description": "Runs a DuckDB query and exposes its result as a named SQL source to descendant components.",
  "properties": {
    "maxRows": {
      "default": 10000,
      "description": "Safety limit appended when the SQL has no LIMIT clause. Defaults to 10000.",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991,
      "type": "integer"
    },
    "name": {
      "description": "Logical source name exposed to descendant SQL widgets via {{name}}.",
      "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$",
      "type": "string"
    },
    "sql": {
      "description": "DuckDB SQL query with {{source_name}} and $param_name placeholders. The result becomes available to descendant SQL widgets as {{name}}.",
      "type": "string"
    }
  },
  "required": [
    "sql",
    "name",
    "maxRows"
  ],
  "type": "object"
}
~~~
## transformer

Execute JS in a sandbox, broadcast result to a param.

~~~json
{
  "additionalProperties": false,
  "description": "Non-visual component that runs JavaScript in a sandboxed iframe and broadcasts the return value to a canvas param. Use $param_name to inject canvas param values and {{udf_name}} to inject UDF result rows. UDF data is substituted as a JSON array of row objects, e.g. [{\"col1\":\"a\",\"col2\":1},{\"col1\":\"b\",\"col2\":2}]. The method string should be a self-invoking arrow function, e.g. \"()=>{ return $input; }\".",
  "properties": {
    "maxRows": {
      "default": 10000,
      "description": "Row limit for UDF data queries. Defaults to 10000.",
      "exclusiveMinimum": 0,
      "maximum": 9007199254740991,
      "type": "integer"
    },
    "method": {
      "description": "JavaScript code string. Contains $param_name and {{udf_name}} references that are substituted before execution.",
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter name to broadcast the result to.",
      "type": "string"
    }
  },
  "required": [
    "param",
    "method",
    "maxRows"
  ],
  "type": "object"
}
~~~
## ai-chat

AI chat for connected UDFs.

~~~json
{
  "additionalProperties": false,
  "description": "Always-on AI chat for asking questions about UDFs connected to this JSON UI node.",
  "properties": {
    "description": {
      "description": "Optional helper text displayed beside the chat surface",
      "type": "string"
    },
    "systemPromptExtra": {
      "description": "Optional additional system prompt appended to the AI chat instructions",
      "type": "string"
    },
    "title": {
      "description": "Optional title displayed beside the chat surface",
      "type": "string"
    }
  },
  "type": "object"
}
~~~
## slider

A slider that can optionally sync with canvas parameters. If param is provided, syncs with that parameter or form; otherwise works as a regular slider.

~~~json
{
  "additionalProperties": false,
  "properties": {
    "defaultValue": {
      "default": 0,
      "type": "number"
    },
    "disabled": {
      "default": false,
      "type": "boolean"
    },
    "label": {
      "description": "Label text displayed above the slider",
      "type": "string"
    },
    "max": {
      "default": 100,
      "type": "number"
    },
    "min": {
      "default": 0,
      "type": "number"
    },
    "param": {
      "description": "The canvas parameter name to sync with, or form field name if inside a Form component. If omitted, works as a regular slider.",
      "type": "string"
    },
    "step": {
      "default": 1,
      "type": "number"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"color: red; font-size: 16px\")",
      "type": "string"
    }
  },
  "required": [
    "min",
    "max",
    "step",
    "defaultValue",
    "disabled"
  ],
  "type": "object"
}
~~~
## div

Container for grouping child elements.
- Has children: yes

~~~json
{
  "additionalProperties": false,
  "description": "A generic container for grouping elements. Can contain any child components. Defaults to a flex column.",
  "properties": {
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"display: flex; gap: 8px; padding: 16px\")",
      "type": "string"
    }
  },
  "type": "object"
}
~~~
## image

Display an image from a URL or base64 data URL.

~~~json
{
  "additionalProperties": false,
  "description": "Displays an image from a URL or base64 data URL. Useful for showing pasted images, charts, or any visual asset.",
  "properties": {
    "alt": {
      "description": "Accessible description of the image",
      "type": "string"
    },
    "objectFit": {
      "default": "contain",
      "description": "How the image fits its container",
      "enum": [
        "contain",
        "cover",
        "fill",
        "none",
        "scale-down"
      ],
      "type": "string"
    },
    "src": {
      "description": "Image URL or base64 data URL",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"opacity: 0.8; border-radius: 8px\")",
      "type": "string"
    }
  },
  "required": [
    "src",
    "objectFit"
  ],
  "type": "object"
}
~~~
## map

Live UDF map.

~~~json
{
  "additionalProperties": false,
  "description": "Interactive Mapbox map that syncs viewport bounds [west, south, east, north] with a canvas parameter. Supports auto-send on pan/zoom or manual send via button.",
  "properties": {
    "centerLat": {
      "default": 40.7,
      "type": "number"
    },
    "centerLng": {
      "default": -74,
      "type": "number"
    },
    "label": {
      "description": "Label above the map",
      "type": "string"
    },
    "layers": {
      "items": {
        "anyOf": [
          {
            "additionalProperties": false,
            "properties": {
              "udf": {
                "description": "Name of the UDF",
                "type": "string"
              },
              "visible": {
                "description": "Whether the layer is visible",
                "type": "boolean"
              },
              "vizConfig": {
                "additionalProperties": {},
                "description": "Visualization configuration for the layer",
                "type": "object"
              }
            },
            "required": [
              "udf"
            ],
            "type": "object"
          },
          {
            "description": "Name of the UDF",
            "type": "string"
          }
        ],
        "description": "Layer configuration or UDF name"
      },
      "type": "array"
    },
    "mapStyle": {
      "description": "Map style",
      "enum": [
        "light",
        "dark",
        "satellite",
        "blank"
      ],
      "type": "string"
    },
    "param": {
      "description": "Canvas parameter for bounds [west, south, east, north]",
      "type": "string"
    },
    "sendParam": {
      "default": false,
      "description": "Whether to send the bounds to the canvas",
      "type": "boolean"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px; overflow: hidden\")",
      "type": "string"
    },
    "zoom": {
      "default": 12,
      "type": "number"
    }
  },
  "required": [
    "sendParam",
    "centerLng",
    "centerLat",
    "zoom",
    "layers"
  ],
  "type": "object"
}
~~~
## iframe

Embed a web page or HTML-returning UDF in an iframe using http(s) URLs, $param URL templates, or {{udf}} placeholders.

~~~json
{
  "additionalProperties": false,
  "description": "Embeds a web page or HTML-returning UDF in an iframe. Use for dashboards, docs, or any site that permits framing.",
  "properties": {
    "allow": {
      "description": "Optional allow attribute (e.g. camera; microphone; geolocation)",
      "type": "string"
    },
    "sandbox": {
      "description": "Optional sandbox attribute (space-separated tokens, e.g. allow-scripts allow-same-origin)",
      "type": "string"
    },
    "style": {
      "description": "Inline CSS styles as a plain CSS string (e.g., \"border-radius: 8px\")",
      "type": "string"
    },
    "title": {
      "description": "Accessible title for the embedded content",
      "type": "string"
    },
    "url": {
      "description": "Absolute http or https URL, optionally with $param references, or an exact UDF placeholder like {{udf}} or {{udf?name=$param}}.",
      "type": "string"
    }
  },
  "required": [
    "url"
  ],
  "type": "object"
}
~~~

