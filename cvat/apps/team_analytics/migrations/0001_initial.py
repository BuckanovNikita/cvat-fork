from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TechnicalAccount",
            fields=[
                ("user_id", models.PositiveBigIntegerField(primary_key=True, serialize=False)),
                ("user_name", models.CharField(max_length=150)),
                ("updated_date", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
