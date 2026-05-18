from staff.models import ChatMessage


def chat_unread_counts(request):
    """Provide unread admin chat counts for admin_panel templates."""
    unread_staff_messages = 0
    unread_customer_messages = 0
    total_unread = 0

    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'admin':
        unread_staff_messages = ChatMessage.objects.filter(
            sender__role='staff', receiver__role='admin', is_read=False
        ).count()
        unread_customer_messages = ChatMessage.objects.filter(
            sender__role='customer', receiver__role='admin', is_read=False
        ).count()
        total_unread = unread_staff_messages + unread_customer_messages

    return {
        'unread_staff_messages': unread_staff_messages,
        'unread_customer_messages': unread_customer_messages,
        'total_unread': total_unread,
    }
