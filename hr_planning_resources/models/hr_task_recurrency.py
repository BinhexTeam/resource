from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.date_utils import get_timedelta


class HrTaskRecurrency(models.Model):
    _name = "hr.task.recurrency"
    _description = "Hr Task Recurrency"

    task_ids = fields.One2many(
        comodel_name="hr.task",
        inverse_name="recurrency_id",
        string="Related Planning Tasks",
    )
    repeat_interval = fields.Integer("Repeat Every", default=1, required=True)
    repeat_unit = fields.Selection(
        [
            ("day", "Days"),
            ("week", "Weeks"),
            ("month", "Months"),
            ("year", "Years"),
        ],
        default="week",
        required=True,
    )
    repeat_type = fields.Selection(
        [
            ("forever", "Forever"),
            ("until", "Until"),
            ("x_times", "Number of Repetitions"),
        ],
        string="Weeks",
        default="forever",
    )
    repeat_until = fields.Datetime(
        help="Up to which date should the plannings be repeated",
    )
    repeat_number = fields.Integer(
        string="Repetitions", help="No Of Repetitions of the plannings"
    )
    last_generated_end_datetime = fields.Datetime(
        "Last Generated End Date", readonly=True
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains("repeat_number", "repeat_type")
    def _check_repeat_number(self):
        if self.filtered(lambda t: t.repeat_type == "x_times" and t.repeat_number < 0):
            raise ValidationError(_("The number of repetitions cannot be negative."))

    @api.constrains("company_id", "task_ids")
    def _check_multi_company(self):
        for recurrency in self:
            if any(
                recurrency.company_id != planning.company_id
                for planning in recurrency.task_ids
            ):
                raise ValidationError(
                    _("An shift must be in the same company as its recurrency.")
                )

    def name_get(self):
        result = []
        for recurrency in self:
            if recurrency.repeat_type == "forever":
                name = _(f"Forever, every {recurrency.repeat_interval} week(s)")
            else:
                name = _(
                    f"Every {recurrency.repeat_interval} "
                    "week(s) until {recurrency.repeat_until}"
                )
            result.append([recurrency.id, name])
        return result

    @api.model
    def _cron_schedule_next(self):
        companies = self.env["res.company"].search([])
        now = fields.Datetime.now()
        for company in companies:
            delta = get_timedelta(company.task_generation_interval, "month")

            recurrencies = self.search(
                [
                    "&",
                    "&",
                    ("company_id", "=", company.id),
                    ("last_generated_end_datetime", "<", now + delta),
                    "|",
                    ("repeat_until", "=", False),
                    ("repeat_until", ">", now - delta),
                ]
            )
            recurrencies._repeat_task(now + delta)

    def _repeat_task(self, stop_datetime=False):
        HrTask = self.env["hr.task"]
        for recurrency in self:
            task = self._get_latest_task(recurrency)
            if task:
                recurrence_end_dt = self._get_recurrence_end_datetime(recurrency)
                stop_datetime = self._get_stop_datetime(recurrency, stop_datetime)
                range_limit = min(dt for dt in [recurrence_end_dt, stop_datetime] if dt)
                task_duration = task.date_end - task.date_start

                task_values_list = self._generate_task_values_list(
                    task, recurrency, range_limit, task_duration
                )

                if task_values_list:
                    HrTask.create(task_values_list)
                    recurrency.write(
                        {
                            "last_generated_end_datetime": task_values_list[-1][
                                "date_start"
                            ]
                        }
                    )
            else:
                recurrency.unlink()

    def _get_latest_task(self, recurrency):
        return self.env["hr.task"].search(
            [("recurrency_id", "=", recurrency.id)],
            limit=1,
            order="date_start DESC",
        )

    def _get_recurrence_end_datetime(self, recurrency):
        if recurrency.repeat_type == "until":
            return recurrency.repeat_until
        if recurrency.repeat_type == "x_times":
            return recurrency._get_recurrence_last_datetime()
        return False

    def _get_stop_datetime(self, recurrency, stop_datetime):
        if not stop_datetime:
            stop_datetime = fields.Datetime.now() + get_timedelta(
                recurrency.company_id.task_generation_interval,
                "month",
            )
        return stop_datetime

    def _generate_task_values_list(self, task, recurrency, range_limit, task_duration):
        def get_all_task_next_starts(task, recurrency, range_limit):
            for i in range(1, 365 * 5):
                next_start = self.env["hr.task"]._add_delta_with_dst(
                    task.date_start,
                    get_timedelta(
                        recurrency.repeat_interval * i,
                        recurrency.repeat_unit,
                    ),
                )
                if next_start >= range_limit:
                    return
                yield next_start

        return [
            task.copy_data(
                {
                    "date_start": start,
                    "date_end": start + task_duration,
                    "recurrency_id": recurrency.id,
                    "company_id": recurrency.company_id.id,
                    "repeat": True,
                    "state": "planified",
                }
            )[0]
            for start in get_all_task_next_starts(task, recurrency, range_limit)
        ]

    def _delete_task(self, date_start):
        tasks = self.env["hr.task"].search(
            [
                ("recurrency_id", "in", self.ids),
                ("date_start", ">=", date_start),
                ("state", "=", "planified"),
            ]
        )
        tasks.unlink()

    def _get_recurrence_last_datetime(self):
        self.ensure_one()
        date_end = self.env["hr.task"].search_read(
            [("recurrency_id", "=", self.id)],
            ["date_end"],
            order="date_end",
            limit=1,
        )
        timedelta = get_timedelta(
            self.repeat_number * self.repeat_interval, self.repeat_unit
        )
        if timedelta.days > 999:
            raise ValidationError(
                _(
                    "Recurring shifts cannot be planned further than 999 days in the "
                    "future."
                )
            )
        return date_end[0]["date_end"] + timedelta
