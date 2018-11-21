django.jQuery(function () {
    django.jQuery('#pull-event').click(function() {
        window.location.href = window.location.href.replace('change', 'pull');
    }); 
});