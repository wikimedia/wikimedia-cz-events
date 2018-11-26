from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.urls import reverse
from django import forms
from eventsite.models import Registration, Event, Answer, Question

# Create your views here.

def index(request):
    return render(request, 'index.html')

def answer(request, id, token):
    reg = Registration.from_token(token)
    if request.method == 'POST':
        f = QuestionsForm(request.POST, registration=reg)
        if f.is_valid():
            f.save()
            return HttpResponseRedirect(reverse('verify', kwargs={'id': id, 'token': token}))
        return render(request, 'answer.html', {
            'event': reg.event,
            'registration': reg,
            'form': f,
        })
    else:
        f = QuestionsForm(registration=reg)
    return render(request, 'answer.html', {
        'event': reg.event,
        'registration': reg,
        'form': f,
    })

class QuestionsForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self._registration = kwargs.pop('registration')
        super(QuestionsForm, self).__init__(*args, **kwargs)
        for question in self._registration.event.questions.all():
            if question.name == "Volba jídla" and self._registration.data.get('lunch') == "Ne":
                continue
            if question.type == "open":
                self.fields[question.name] = forms.CharField()
            elif question.type == "close":
                self.fields[question.name] = forms.ChoiceField(choices=question.get_choices())
    
    def save(self):
        for question_text in self.cleaned_data:
            question = Question.objects.get(name=question_text)
            answer = question.possible_answers[int(self.cleaned_data[question_text].replace('answer_', ''))]
            cur = self._registration.answers.filter(question=question)
            if len(cur) == 0:
                self._registration.answers.create(question=question, answer=answer)
            else:
                cur[0].answer = answer
                cur[0].save()


def verify(request, id, token):
    reg = Registration.from_token(token)
    if len(reg.event.questions.all()) != len(reg.answers.all()):
        return HttpResponseRedirect(reverse('answer', kwargs={'id': reg.id, 'token': token}))
    if reg.verified:
        return HttpResponseRedirect(reg.event.already_confirmed_url)
    if reg.verify_token() == token:
        reg.verified = True
        reg.save()
        return HttpResponseRedirect(reg.event.successfully_confirmed_url)
    else:
        return HttpResponseRedirect(reg.event.invalid_token_url)
