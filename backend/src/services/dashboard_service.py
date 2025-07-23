import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List

import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Template
from plotly.offline import plot

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self):
        self.template_loader = Template(self._get_html_template())

    async def create_dashboard(
        self, summary_data: Dict, dashboard_type: str = "cost_optimization", dashboard_name: str = "costAnalysis"
    ) -> str:
        """Create interactive dashboard from summary data."""

        # Check if this is a raw data fallback case
        if summary_data.get("status") in ["raw_data_fallback", "raw_data_preservation"]:
            # Pass dashboard_name to the raw data dashboard method
            summary_data["dashboard_name"] = dashboard_name
            return await self._create_raw_data_dashboard(summary_data)

        # Parse data and create visualizations for normal dashboard
        charts = await self._create_charts(summary_data, dashboard_type)

        # Generate unique dashboard ID using provided name
        readable_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_id = f"{dashboard_name}_{readable_timestamp}"

        # Generate HTML with embedded charts
        dashboard_html = self.template_loader.render(
            title=f"Cost Optimization Dashboard - {datetime.now().strftime('%Y-%m-%d')}",
            dashboard_id=dashboard_id,
            charts=charts,
            summary=summary_data.get("executive_summary", "No summary available"),
            recommendations=summary_data.get("recommendations", []),
            key_metrics=summary_data.get("key_metrics", {}),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        return dashboard_html

    async def _create_charts(self, data: Dict, dashboard_type: str) -> List[str]:
        """Create Plotly charts based on data and dashboard type."""
        charts = []

        try:
            if dashboard_type == "cost_optimization":
                # Cost savings chart
                if "cost_savings" in data and data["cost_savings"]:
                    fig = px.bar(
                        x=list(data["cost_savings"].keys()),
                        y=list(data["cost_savings"].values()),
                        title="Potential Cost Savings by Category",
                        labels={"x": "Category", "y": "Savings ($)"},
                        color=list(data["cost_savings"].values()),
                        color_continuous_scale="Viridis",
                    )
                    fig.update_layout(
                        showlegend=False,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    charts.append(plot(fig, output_type="div", include_plotlyjs=False))

                # Resource utilization chart
                if "utilization_data" in data and data["utilization_data"]:
                    util_data = data["utilization_data"]
                    if "cpu_usage" in util_data and "timestamps" in util_data:
                        fig = go.Figure(
                            data=go.Scatter(
                                x=util_data["timestamps"],
                                y=util_data["cpu_usage"],
                                mode="lines+markers",
                                name="CPU Utilization (%)",
                                line=dict(color="#1f77b4", width=3),
                            )
                        )
                        fig.update_layout(
                            title="Resource Utilization Over Time",
                            xaxis_title="Time",
                            yaxis_title="Utilization (%)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                        )
                        charts.append(
                            plot(fig, output_type="div", include_plotlyjs=False)
                        )

                # Recommendations priority chart
                if "recommendations" in data and data["recommendations"]:
                    rec_data = data["recommendations"][:5]  # Top 5 recommendations
                    categories = [rec.get("category", "Unknown") for rec in rec_data]
                    savings = [rec.get("estimated_savings", 0) for rec in rec_data]

                    fig = px.horizontal_bar(
                        x=savings,
                        y=categories,
                        title="Top 5 Recommendations by Estimated Savings",
                        labels={"x": "Estimated Savings ($)", "y": "Category"},
                        color=savings,
                        color_continuous_scale="RdYlGn",
                    )
                    fig.update_layout(
                        showlegend=False,
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    charts.append(plot(fig, output_type="div", include_plotlyjs=False))

                # Key metrics gauge charts
                if "key_metrics" in data and data["key_metrics"]:
                    metrics = data["key_metrics"]
                    if "total_savings" in metrics:
                        fig = go.Figure(
                            go.Indicator(
                                mode="gauge+number+delta",
                                value=metrics["total_savings"],
                                domain={"x": [0, 1], "y": [0, 1]},
                                title={"text": "Total Potential Savings ($)"},
                                gauge={
                                    "axis": {
                                        "range": [
                                            None,
                                            metrics.get(
                                                "max_savings",
                                                metrics["total_savings"] * 1.5,
                                            ),
                                        ]
                                    },
                                    "bar": {"color": "darkgreen"},
                                    "steps": [
                                        {
                                            "range": [
                                                0,
                                                metrics["total_savings"] * 0.5,
                                            ],
                                            "color": "lightgray",
                                        },
                                        {
                                            "range": [
                                                metrics["total_savings"] * 0.5,
                                                metrics["total_savings"],
                                            ],
                                            "color": "gray",
                                        },
                                    ],
                                    "threshold": {
                                        "line": {"color": "red", "width": 4},
                                        "thickness": 0.75,
                                        "value": metrics["total_savings"] * 0.9,
                                    },
                                },
                            )
                        )
                        fig.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            height=300,
                        )
                        charts.append(
                            plot(fig, output_type="div", include_plotlyjs=False)
                        )

        except Exception as e:
            logger.error(f"Error creating charts: {e}")
            # Add a fallback chart
            fig = go.Figure()
            fig.add_annotation(
                text="Dashboard data is being processed...",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                xanchor="center",
                yanchor="middle",
                showarrow=False,
                font_size=16,
            )
            fig.update_layout(
                title="Dashboard Loading",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
            )
            charts.append(plot(fig, output_type="div", include_plotlyjs=False))

        return charts

    async def _create_raw_data_dashboard(self, data: Dict) -> str:
        """Creates a dashboard HTML specifically for raw data fallback cases."""
        # Use consistent naming for fallback cases  
        readable_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_name = data.get("dashboard_name", "costAnalysis")
        dashboard_id = f"{dashboard_name}_{readable_timestamp}_fallback"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        status = data.get("status", "unknown")
        reason = data.get("reason", "No reason provided")
        
        # Create raw data visualization
        raw_data_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Raw Data Debug Dashboard - {datetime.now().strftime('%Y-%m-%d')}</title>
            <style>
                body {{ 
                    font-family: 'Courier New', monospace;
                    line-height: 1.6;
                    color: #333;
                    background: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: #e74c3c;
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .status {{
                    background: #f39c12;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .raw-data {{
                    background: #2c3e50;
                    color: #ecf0f1;
                    padding: 20px;
                    border-radius: 5px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    font-size: 12px;
                    line-height: 1.4;
                    max-height: 600px;
                    overflow-y: auto;
                }}
                .debug-info {{
                    background: #3498db;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                .extracted-fragments {{
                    background: #27ae60;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 20px 0;
                }}
                pre {{
                    margin: 0;
                    font-family: inherit;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔍 Raw Data Debug Dashboard</h1>
                    <p>Generated on {timestamp}</p>
                    <p>Dashboard ID: {dashboard_id}</p>
                </div>
                
                <div class="status">
                    <h3>Status: {status}</h3>
                    <p><strong>Reason:</strong> {reason}</p>
                </div>
        """
        
        # Add extracted fragments if available
        if "extracted_fragments" in data:
            fragments = data["extracted_fragments"]
            raw_data_html += f"""
                <div class="extracted-fragments">
                    <h3>🔎 Extracted Fragments</h3>
                    <p><strong>Numbers Found:</strong> {fragments.get('any_numbers_found', [])}</p>
                    <p><strong>Resource IDs:</strong> {fragments.get('any_resource_ids_found', [])}</p>
                    <p><strong>Services:</strong> {fragments.get('any_service_names_found', [])}</p>
                    <p><strong>Errors:</strong> {fragments.get('any_error_messages', [])}</p>
                </div>
            """
        
        # Add debug info if available
        if "debug_info" in data or "debug_analysis" in data:
            debug_info = data.get("debug_info", data.get("debug_analysis", {}))
            raw_data_html += f"""
                <div class="debug-info">
                    <h3>🛠 Debug Information</h3>
                    <pre>{json.dumps(debug_info, indent=2)}</pre>
                </div>
            """
        
        # Add the raw input data
        raw_input = data.get("raw_input_data", data.get("amazon_q_responses", "No raw data available"))
        raw_data_html += f"""
                <div class="raw-data">
                    <h3>📄 Raw Input Data</h3>
                    <pre>{raw_input}</pre>
                </div>
                
                <div style="margin-top: 30px; padding: 20px; background: #ecf0f1; border-radius: 5px;">
                    <h3>💡 What to do next:</h3>
                    <ul>
                        <li>Check if Amazon Q CLI is properly configured and accessible</li>
                        <li>Verify AWS credentials and permissions</li>
                        <li>Review the raw data above for any error messages or clues</li>
                        <li>Try running the cost optimization query again with different parameters</li>
                        <li>Check the Amazon Q service logs for more details</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        return raw_data_html

    def _get_html_template(self) -> str:
        """HTML template for React-ready dashboard with static serving optimization."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
            <!-- React Runtime and Chart Libraries for Static Serving -->
            <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
            <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body { 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    min-height: 100vh;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }
                
                .header { 
                    text-align: center;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .header h1 {
                    color: #2c3e50;
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                
                .header .timestamp {
                    color: #7f8c8d;
                    font-size: 0.9em;
                }
                
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                
                .metric-card {
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    text-align: center;
                    transition: transform 0.3s ease;
                }
                
                .metric-card:hover {
                    transform: translateY(-5px);
                }
                
                .metric-value {
                    font-size: 2.5em;
                    font-weight: bold;
                    color: #27ae60;
                    margin-bottom: 10px;
                }
                
                .metric-label {
                    color: #7f8c8d;
                    font-size: 0.9em;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }
                
                .summary { 
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .summary h2 {
                    color: #2c3e50;
                    margin-bottom: 20px;
                    font-size: 1.8em;
                }
                
                .chart-container { 
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .recommendations { 
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .recommendations h2 {
                    color: #2c3e50;
                    margin-bottom: 25px;
                    font-size: 1.8em;
                }
                
                .recommendation-item { 
                    margin-bottom: 20px;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border-left: 4px solid #3498db;
                    transition: all 0.3s ease;
                }
                
                .recommendation-item:hover {
                    background: #e9ecef;
                    border-left-color: #2980b9;
                }
                
                .recommendation-category {
                    font-weight: bold;
                    color: #2c3e50;
                    font-size: 1.1em;
                    margin-bottom: 8px;
                }
                
                .recommendation-description {
                    color: #495057;
                    margin-bottom: 10px;
                    line-height: 1.6;
                }
                
                .recommendation-savings {
                    color: #27ae60;
                    font-weight: bold;
                    font-size: 1.1em;
                }
                
                .footer {
                    text-align: center;
                    padding: 30px;
                    color: #7f8c8d;
                    font-size: 0.9em;
                }
                
                .embed-info {
                    background: #e8f4fd;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    border: 1px solid #b8daff;
                }
                
                .embed-info h3 {
                    color: #004085;
                    margin-bottom: 10px;
                }
                
                .embed-code {
                    background: #f8f9fa;
                    padding: 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 0.85em;
                    word-break: break-all;
                    border: 1px solid #dee2e6;
                }
                
                @media (max-width: 768px) {
                    .container {
                        padding: 10px;
                    }
                    
                    .header h1 {
                        font-size: 2em;
                    }
                    
                    .metrics-grid {
                        grid-template-columns: 1fr;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1><i class="fas fa-chart-line"></i> {{ title }}</h1>
                    <div class="timestamp">Generated on {{ timestamp }}</div>
                </div>
                
                {% if key_metrics %}
                <div class="metrics-grid">
                    {% for metric, value in key_metrics.items() %}
                    <div class="metric-card">
                        <div class="metric-value">{{ value }}</div>
                        <div class="metric-label">{{ metric.replace('_', ' ').title() }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <div class="summary">
                    <h2><i class="fas fa-file-alt"></i> Executive Summary</h2>
                    <p>{{ summary }}</p>
                </div>
                
                {% for chart in charts %}
                <div class="chart-container">
                    {{ chart|safe }}
                </div>
                {% endfor %}
                
                <div class="recommendations">
                    <h2><i class="fas fa-lightbulb"></i> Recommendations</h2>
                    {% for rec in recommendations %}
                    <div class="recommendation-item">
                        <div class="recommendation-category">
                            <i class="fas fa-arrow-right"></i> {{ rec.category }}
                        </div>
                        <div class="recommendation-description">{{ rec.description }}</div>
                        {% if rec.estimated_savings %}
                        <div class="recommendation-savings">
                            <i class="fas fa-dollar-sign"></i> Estimated Savings: ${{ rec.estimated_savings }}
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                
                <div class="embed-info">
                    <h3><i class="fas fa-code"></i> Embed This Dashboard</h3>
                    <p>Use this code to embed the dashboard in your website:</p>
                    <div class="embed-code">
                        &lt;iframe src="[DASHBOARD_URL]" width="100%" height="600px" frameborder="0" allowfullscreen&gt;&lt;/iframe&gt;
                    </div>
                </div>
                
                <div class="footer">
                    <p>Dashboard ID: {{ dashboard_id }} | Powered by Amazon Q + Bedrock Analytics</p>
                    <p><small>Static React Dashboard - Optimized for Embedding</small></p>
                </div>
            </div>
            
            <!-- Dashboard Data for React Components -->
            <script type="application/json" id="dashboard-data">
                {
                    "title": "{{ title }}",
                    "dashboard_id": "{{ dashboard_id }}",
                    "timestamp": "{{ timestamp }}",
                    "summary": {{ summary | tojson }},
                    "key_metrics": {{ key_metrics | tojson }},
                    "recommendations": {{ recommendations | tojson }}
                }
            </script>
            
            <!-- React Dashboard Component Initialization -->
            <script>
                // This script ensures the dashboard is ready for React rendering if needed
                window.DashboardData = JSON.parse(document.getElementById('dashboard-data').textContent);
                
                // Event for external React apps to hook into
                window.dispatchEvent(new CustomEvent('dashboardReady', { 
                    detail: window.DashboardData 
                }));
                
                console.log('React-ready dashboard loaded with data:', window.DashboardData);
            </script>
        </body>
        </html>
        """

    def get_static_assets(self) -> Dict[str, str]:
        """Return additional CSS/JS files optimized for React static serving."""
        return {
            "styles.css": """
                /* Enhanced styles for React dashboard static serving */
                .highlight { background-color: #fff3cd; padding: 2px 4px; border-radius: 3px; }
                .metric { font-size: 1.2em; font-weight: bold; color: #007bff; }
                .loading { text-align: center; padding: 50px; color: #6c757d; }
                .error { background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0; }
                
                /* React component ready styles */
                .react-dashboard-root { width: 100%; height: 100%; }
                .chart-responsive { width: 100%; min-height: 300px; }
                .dashboard-embed { border: none; overflow: hidden; }
                
                /* Mobile-first responsive design for static serving */
                @media (max-width: 480px) {
                    .metrics-grid { grid-template-columns: 1fr; gap: 10px; }
                    .container { padding: 10px; }
                    .chart-container { padding: 15px; }
                }
            """,
            "dashboard.js": """
                // React dashboard utilities for static serving
                window.DashboardUtils = {
                    formatCurrency: function(amount) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'currency',
                            currency: 'USD'
                        }).format(amount);
                    },
                    
                    formatPercentage: function(value) {
                        return new Intl.NumberFormat('en-US', {
                            style: 'percent',
                            minimumFractionDigits: 1
                        }).format(value / 100);
                    },
                    
                    // Hook for external React applications
                    onReactMount: function(callback) {
                        if (window.DashboardData) {
                            callback(window.DashboardData);
                        } else {
                            window.addEventListener('dashboardReady', function(event) {
                                callback(event.detail);
                            });
                        }
                    }
                };
                
                // Enable smooth scrolling for static serving
                document.addEventListener('DOMContentLoaded', function() {
                    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                        anchor.addEventListener('click', function (e) {
                            e.preventDefault();
                            document.querySelector(this.getAttribute('href')).scrollIntoView({
                                behavior: 'smooth'
                            });
                        });
                    });
                });
            """,
            "manifest.json": json.dumps({
                "name": "Cost Optimization Dashboard",
                "short_name": "Dashboard",
                "description": "AWS Cost Optimization Dashboard powered by Amazon Q and Bedrock",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#ffffff",
                "theme_color": "#2c3e50",
                "icons": []
            })
        }
