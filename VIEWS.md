For models:

1. Keep the EmployeeProfile model in employees/models.py
2. In accounts/models.py, import it: from employees.models import EmployeeProfile

3. Don't extend it, just use it directly



For views:

1. keep the views in the accounts/views.py and delete the views in employees/views.py
2. Remove the urls for those views since everything is now handled in the accounts app



For forms:

1. Keep the EmployeeUpdateForm in accounts/forms.py with our activation status synchronization
3. Remove the duplicate EmployeeUpdateForm from employees/forms.py
  THERE IS NO NEED TO IMPORT IT SINCE BOTH ARE DOING EXACTLY SAME THING