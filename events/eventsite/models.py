from django.db import models
from jsonfield import JSONField
from django.conf import settings
from eventsite.google import get_google_service, get_range_from_spreadsheet, column_map
from eventsite.helpers import send_mass_html_mail
from django.template import Context, Template
import hashlib

MAIL_TYPES = (
    ('confirm', 'Confirm registration'),
    ('verify', 'Verify registration')
)

QUESTION_TYPES = (
    ('open', 'Open-ended question'),
    ('close', 'Close-ended question'),
)

class MailText(models.Model):
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    mail_type = models.CharField(max_length=255, choices=MAIL_TYPES)
    text = models.TextField(help_text="This has same syntax like Django's templates. You can use any data from registration JSON here", null=False, blank=True)

class Question(models.Model):
    name = models.CharField(max_length=255, null=False)
    type = models.CharField(max_length=255, null=False, choices=QUESTION_TYPES)
    possible_answers = JSONField(default=[])

    def get_choices(self):
        res = []
        for i, possible_answer in enumerate(self.possible_answers):
            res.append(("answer_%s" % i, possible_answer))
        return res

    def __str__(self):
        return self.name

class Answer(models.Model):
    question = models.ForeignKey('Question', on_delete=models.CASCADE)
    answer = models.CharField(max_length=255, null=False, blank=True)

    def __str__(self):
        return "Answer to %s" % self.question

class Event(models.Model):
    google_table = models.CharField(max_length=255, null=False)
    name = models.CharField(max_length=255, null=False)
    list_name = models.CharField(max_length=255, null=False, blank=True)
    header = JSONField(default=[])
    skip_rows = models.IntegerField(default=0)
    from_mail = models.CharField(max_length=255, null=False, blank=True) # TODO: Validate mail address here
    questions = models.ManyToManyField('Question', blank=True)
    successfully_confirmed_url = models.CharField(max_length=255, null=False, blank=True)
    invalid_token_url = models.CharField(max_length=255, null=False, blank=True)
    already_confirmed_url = models.CharField(max_length=255, null=False, blank=True)

    def __str__(self):
        return self.name
    
    def mail_participants(self, mail_type, debug_to=None):
        subjects = {
            'verify': "[%s] %s se blíží, plánujete se zúčastnit?" % (self.name, self.name),
            "confirm": "[%s] Potvrzení registrace" % self.name,
        }
        mails = []
        html_template = Template(self.mailtext_set.get(mail_type=mail_type).text)
        for reg in self.registration_set.all():
            if (mail_type == "confirm" and reg.confirmed) or (mail_type == "verified" and reg.verified):
                continue
            c_dict = {
                'greeting': reg.greeting(),
                "verify_link": reg.verify_link(),
            }
            for key in reg.data:
                c_dict[key] = reg.data[key]
            c = Context(c_dict)
            html = html_template.render(c)
            if debug_to:
                actual_mail = debug_to
            else:
                actual_mail = reg.data.get('email')
            mails.append((subjects[mail_type], html, self.from_mail, [actual_mail]))

            if mail_type == "confirm":
                reg.confirmed = True
                reg.save()

            break
        return send_mass_html_mail(mails)
    
    def pull(self):
        service = get_google_service('sheets', 'v4')
        confirmed_regs = self.registration_set.filter(confirmed=True)
        confirmed_rows = []
        for reg in confirmed_regs:
            confirmed_rows.append(reg.row)
        del(confirmed_regs)

        self.registration_set.all().delete()

        header = get_range_from_spreadsheet(self.google_table, self.list_name, 'A1:T1', service)[0]
        if header is None:
            return # TODO: Raise error
        
        if self.header != header:
            self.header = header
            self.save()
        
        row_num = 2 + self.skip_rows
        while True:
            rows = get_range_from_spreadsheet(self.google_table, self.list_name, 'A%s:T%s' % (str(row_num), str(row_num + 30)), service)
            if rows is None:
                break
            for row in rows:
                reg_data = {}
                i = 0
                for item in row:
                    if i >= len(header):
                        break # we are out of header, which always mean notes we won't need
                    if header[i] in column_map:
                        if column_map[header[i]] in reg_data:
                            continue # T207896
                        reg_data[column_map[header[i]]] = item
                    i += 1
                confirmed = row_num in confirmed_rows
                reg = Registration.objects.create(event=self, data=reg_data, row=row_num, confirmed=confirmed)
                reg.save()
                row_num += 1


class Registration(models.Model):
    event = models.ForeignKey('Event', on_delete=models.CASCADE)
    row = models.IntegerField()
    data = JSONField(default={})
    verified = models.BooleanField(default=False)
    confirmed = models.BooleanField(default=False)
    answers = models.ManyToManyField('Answer')

    def __str__(self):
        return '%s, %s' % (self.full_name(), self.event)

    def full_name(self):
        return '%s %s' % (self.data.get('first_name'), self.data.get('last_name'))
    
    def greeting(self):
        if self.data.get('sex') == "Muž":
            return "Vážený pane %s," % self.data.get('last_name')
        elif self.data.get('sex') == "Zena":
            return "Vážená paní %s," % self.data.get('last_name')
    
    def verify_link(self):
        return 'https://events.wikimedia.cz/verify/%d/%s' % (self.id, self.verify_token())
    
    def verify_token(self):
        return hashlib.md5((self.data.get('email').encode('utf-8') + settings.SECRET_KEY.encode('utf-8'))).hexdigest()
