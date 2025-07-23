import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List

from jinja2 import Template

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

        # Generate unique dashboard ID using provided name
        readable_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dashboard_id = f"{dashboard_name}_{readable_timestamp}"

        # Extract actionable recommendations for simplified display
        recommendations = summary_data.get("priority_recommendations", summary_data.get("actionable_recommendations", []))
        total_savings = summary_data.get("total_cost_savings", summary_data.get("total_savings", {}))
        quick_wins = summary_data.get("quick_wins", [])
        implementation_plan = summary_data.get("implementation_plan", {})

        # Generate HTML focused on actionable recommendations
        dashboard_html = self.template_loader.render(
            title=f"Cost Optimization Dashboard - {datetime.now().strftime('%Y-%m-%d')}",
            dashboard_id=dashboard_id,
            executive_summary=summary_data.get("executive_summary", "Cost optimization analysis completed."),
            total_savings=total_savings,
            recommendations=recommendations,
            quick_wins=quick_wins,
            implementation_plan=implementation_plan,
            savings_by_service=summary_data.get("savings_by_service", {}),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        return dashboard_html

    async def _create_charts(self, data: Dict, dashboard_type: str) -> List[str]:
        """Create simple visualizations (deprecated - now focused on actionable recommendations)."""
        # This method is deprecated in favor of actionable recommendations
        # Return empty list as charts are no longer needed
        logger.info("Chart generation skipped - focusing on actionable recommendations")
        return []

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
        """HTML template for actionable cost optimization dashboard."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ title }}</title>
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
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .header h1 {
                    color: #2c3e50;
                    font-size: 2.5em;
                    margin-bottom: 10px;
                }
                
                .timestamp {
                    color: #7f8c8d;
                    font-size: 0.9em;
                }
                
                .savings-summary {
                    background: linear-gradient(135deg, #27ae60, #2ecc71);
                    color: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                    text-align: center;
                }
                
                .savings-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }
                
                .savings-metric {
                    background: rgba(255,255,255,0.2);
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                }
                
                .savings-value {
                    font-size: 2.2em;
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                
                .savings-label {
                    font-size: 0.9em;
                    opacity: 0.9;
                }
                
                .executive-summary { 
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .section-title {
                    color: #2c3e50;
                    font-size: 1.8em;
                    margin-bottom: 20px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                
                .recommendations-grid {
                    display: grid;
                    gap: 20px;
                    margin-bottom: 30px;
                }
                
                .recommendation-card {
                    background: white;
                    padding: 25px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    border-left: 5px solid #3498db;
                    position: relative;
                }
                
                .recommendation-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                }
                
                .recommendation-rank {
                    background: linear-gradient(135deg, #3498db, #2980b9);
                    color: white;
                    padding: 8px 15px;
                    border-radius: 50px;
                    font-weight: bold;
                    font-size: 0.9em;
                }
                
                .monthly-saving {
                    background: linear-gradient(135deg, #27ae60, #2ecc71);
                    color: white;
                    padding: 8px 15px;
                    border-radius: 50px;
                    font-weight: bold;
                }
                
                .resource-info {
                    margin-bottom: 15px;
                }
                
                .resource-id {
                    font-family: 'Courier New', monospace;
                    background: #f8f9fa;
                    padding: 5px 10px;
                    border-radius: 5px;
                    font-size: 0.9em;
                    color: #e74c3c;
                    font-weight: bold;
                }
                
                .resource-type {
                    background: #3498db;
                    color: white;
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 0.8em;
                    margin-left: 10px;
                }
                
                .implementation-steps {
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 10px;
                    margin-top: 15px;
                }
                
                .step {
                    padding: 8px 0;
                    border-bottom: 1px solid #dee2e6;
                }
                
                .step:last-child {
                    border-bottom: none;
                }
                
                .step-number {
                    background: #3498db;
                    color: white;
                    padding: 2px 8px;
                    border-radius: 50%;
                    font-size: 0.8em;
                    margin-right: 10px;
                    font-weight: bold;
                }
                
                .quick-wins {
                    background: linear-gradient(135deg, #f39c12, #e67e22);
                    color: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .quick-win-item {
                    background: rgba(255,255,255,0.2);
                    padding: 15px;
                    border-radius: 10px;
                    margin-bottom: 15px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                
                .services-breakdown {
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .service-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 15px;
                    border-bottom: 1px solid #ecf0f1;
                }
                
                .service-item:last-child {
                    border-bottom: none;
                }
                
                .service-name {
                    font-weight: bold;
                    color: #2c3e50;
                }
                
                .service-saving {
                    background: #27ae60;
                    color: white;
                    padding: 5px 12px;
                    border-radius: 20px;
                    font-weight: bold;
                }
                
                .implementation-timeline {
                    background: white;
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
                    margin-bottom: 30px;
                }
                
                .timeline-section {
                    margin-bottom: 20px;
                }
                
                .timeline-title {
                    color: #2c3e50;
                    font-weight: bold;
                    margin-bottom: 10px;
                    padding: 10px 15px;
                    background: #ecf0f1;
                    border-radius: 8px;
                }
                
                .timeline-item {
                    padding: 8px 0;
                    padding-left: 20px;
                    border-left: 3px solid #3498db;
                    margin-left: 10px;
                }
                
                .footer {
                    text-align: center;
                    padding: 30px;
                    color: white;
                    font-size: 0.9em;
                    background: rgba(255,255,255,0.1);
                    border-radius: 15px;
                }
                
                .risk-badge {
                    padding: 3px 8px;
                    border-radius: 3px;
                    font-size: 0.8em;
                    font-weight: bold;
                }
                
                .risk-low { background: #27ae60; color: white; }
                .risk-medium { background: #f39c12; color: white; }
                .risk-high { background: #e74c3c; color: white; }
                
                @media (max-width: 768px) {
                    .container { padding: 10px; }
                    .header h1 { font-size: 2em; }
                    .savings-grid { grid-template-columns: 1fr; }
                    .recommendation-header { flex-direction: column; gap: 10px; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <!-- Header -->
                <div class="header">
                    <h1><i class="fas fa-dollar-sign"></i> {{ title }}</h1>
                    <div class="timestamp">Generated on {{ timestamp }}</div>
                </div>
                
                <!-- Total Savings Summary -->
                {% if total_savings %}
                <div class="savings-summary">
                    <h2><i class="fas fa-piggy-bank"></i> Total Cost Savings Potential</h2>
                    <div class="savings-grid">
                        {% if total_savings.monthly_savings %}
                        <div class="savings-metric">
                            <div class="savings-value">${{ total_savings.monthly_savings }}</div>
                            <div class="savings-label">Monthly Savings</div>
                        </div>
                        {% endif %}
                        {% if total_savings.yearly_savings %}
                        <div class="savings-metric">
                            <div class="savings-value">${{ total_savings.yearly_savings }}</div>
                            <div class="savings-label">Yearly Savings</div>
                        </div>
                        {% endif %}
                        {% if total_savings.number_of_opportunities %}
                        <div class="savings-metric">
                            <div class="savings-value">{{ total_savings.number_of_opportunities }}</div>
                            <div class="savings-label">Opportunities</div>
                        </div>
                        {% endif %}
                        {% if total_savings.highest_single_saving %}
                        <div class="savings-metric">
                            <div class="savings-value">${{ total_savings.highest_single_saving }}</div>
                            <div class="savings-label">Biggest Single Win</div>
                        </div>
                        {% endif %}
                    </div>
                </div>
                {% endif %}
                
                <!-- Executive Summary -->
                <div class="executive-summary">
                    <h2 class="section-title"><i class="fas fa-file-alt"></i> Executive Summary</h2>
                    <p>{{ executive_summary }}</p>
                </div>
                
                <!-- Quick Wins -->
                {% if quick_wins %}
                <div class="quick-wins">
                    <h2 class="section-title"><i class="fas fa-bolt"></i> Quick Wins - Implement Now</h2>
                    {% for win in quick_wins %}
                    <div class="quick-win-item">
                        <div>
                            <strong>{{ win.action }}</strong>
                            <br><small>Time needed: {{ win.time_needed }}</small>
                        </div>
                        <div class="monthly-saving">{{ win.saving }}</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <!-- Priority Recommendations -->
                {% if recommendations %}
                <div class="recommendations-grid">
                    <h2 class="section-title"><i class="fas fa-lightbulb"></i> Priority Recommendations</h2>
                    {% for rec in recommendations %}
                    <div class="recommendation-card">
                        <div class="recommendation-header">
                            <div class="recommendation-rank">Rank #{{ rec.rank or loop.index }}</div>
                            <div class="monthly-saving">${{ rec.monthly_saving }}/month</div>
                        </div>
                        
                        <div class="resource-info">
                            <span class="resource-id">{{ rec.resource_id }}</span>
                            <span class="resource-type">{{ rec.resource_type }}</span>
                            {% if rec.risk_assessment %}
                            <span class="risk-badge risk-{{ rec.risk_assessment.lower() }}">{{ rec.risk_assessment }} Risk</span>
                            {% endif %}
                        </div>
                        
                        <div style="margin-bottom: 15px;">
                            <strong>Action:</strong> {{ rec.action_summary }}
                            {% if rec.implementation_time %}
                            <br><small><i class="fas fa-clock"></i> Time needed: {{ rec.implementation_time }}</small>
                            {% endif %}
                        </div>
                        
                        {% if rec.step_by_step %}
                        <div class="implementation-steps">
                            <strong><i class="fas fa-list-ol"></i> Implementation Steps:</strong>
                            {% for step in rec.step_by_step %}
                            <div class="step">
                                <span class="step-number">{{ loop.index }}</span>{{ step }}
                            </div>
                            {% endfor %}
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <!-- Savings by Service -->
                {% if savings_by_service %}
                <div class="services-breakdown">
                    <h2 class="section-title"><i class="fas fa-chart-pie"></i> Savings by AWS Service</h2>
                    {% for service, saving in savings_by_service.items() %}
                    {% if saving > 0 %}
                    <div class="service-item">
                        <span class="service-name">{{ service }}</span>
                        <span class="service-saving">${{ saving }}/month</span>
                    </div>
                    {% endif %}
                    {% endfor %}
                </div>
                {% endif %}
                
                <!-- Implementation Timeline -->
                {% if implementation_plan %}
                <div class="implementation-timeline">
                    <h2 class="section-title"><i class="fas fa-calendar-alt"></i> Implementation Plan</h2>
                    
                    {% if implementation_plan.immediate_actions %}
                    <div class="timeline-section">
                        <div class="timeline-title"><i class="fas fa-play"></i> Start Immediately</div>
                        {% for action in implementation_plan.immediate_actions %}
                        <div class="timeline-item">{{ action }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    {% if implementation_plan.this_week %}
                    <div class="timeline-section">
                        <div class="timeline-title"><i class="fas fa-calendar-week"></i> This Week</div>
                        {% for action in implementation_plan.this_week %}
                        <div class="timeline-item">{{ action }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    {% if implementation_plan.this_month %}
                    <div class="timeline-section">
                        <div class="timeline-title"><i class="fas fa-calendar"></i> This Month</div>
                        {% for action in implementation_plan.this_month %}
                        <div class="timeline-item">{{ action }}</div>
                        {% endfor %}
                    </div>
                    {% endif %}
                    
                    {% if implementation_plan.total_time_investment %}
                    <div style="text-align: center; margin-top: 20px; padding: 15px; background: #ecf0f1; border-radius: 8px;">
                        <strong>Total time investment: {{ implementation_plan.total_time_investment }}</strong>
                    </div>
                    {% endif %}
                </div>
                {% endif %}
                
                <!-- Footer -->
                <div class="footer">
                    <p>Dashboard ID: {{ dashboard_id }} | Powered by Amazon Q + Bedrock Analytics</p>
                    <p><small>Focus on actionable cost savings - No complex charts, just results!</small></p>
                </div>
            </div>
        </body>
        </html>
        """

    def get_static_assets(self) -> Dict[str, str]:
        """Return additional CSS/JS files optimized for React static serving (deprecated)."""
        # This method is deprecated as we now use simple HTML dashboards
        return {}
