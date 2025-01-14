{
    "name": "HR Resource Planner",
    "summary": "",
    "version": "16.0.1.0.7",
    "category": "Human Resources",
    "website": "https://github.com/OCA/resource",
    "author": "Binhex, Odoo Community Association (OCA)",
    "depends": [
        "hr_planning_oca",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_task_ir_cron.xml",
        "views/hr_task_views.xml",
        "views/project_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/create_hr_task_views.xml",
        "views/menus.xml",
    ],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "hr_planning_resources/static/src/scss/hr_planning_resources.scss",
            "hr_planning_resources/static/src/js/*.js",
            "hr_planning_resources/static/src/xml/*.xml",
        ],
    },
}
