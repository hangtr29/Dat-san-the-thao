from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('facilities', '0008_facility_description_facility_highlights_coupon_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='facility',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Ngày đăng ký'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='facility',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now, verbose_name='Cập nhật lần cuối'),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='facility',
            options={'ordering': ['-created_at'], 'verbose_name': 'Cụm sân', 'verbose_name_plural': 'Danh sách cụm sân'},
        ),
    ]
