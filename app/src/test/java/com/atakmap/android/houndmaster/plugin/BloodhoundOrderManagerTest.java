package com.atakmap.android.houndmaster.plugin;

import android.os.Bundle;

import org.junit.After;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

public class BloodhoundOrderManagerTest {
    private final BloodhoundOrderManager manager = BloodhoundOrderManager.getInstance();

    @After
    public void clearOrders() {
        for (BloodhoundOrder order : manager.getOrders())
            manager.removeOrder(order);
        manager.initialize(null);
    }

    @Test
    public void shortRepliesAdvanceOnlyOneOpenOrderFromSender() {
        BloodhoundOrder order = new BloodhoundOrder("S-F", "ODIN", BloodhoundOrder.Status.Sent);
        manager.addOrder(order);

        reply("rGr", "ODIN");
        assertEquals(BloodhoundOrder.Status.Bloodhounding, order.getStatus());
        reply("nPos", "ODIN");
        assertEquals(BloodhoundOrder.Status.Complete, order.getStatus());
        reply("Roger", "ODIN");
        assertEquals(BloodhoundOrder.Status.Complete, order.getStatus());
    }

    @Test
    public void ambiguousBareReplyDoesNotChangeOrders() {
        BloodhoundOrder first = new BloodhoundOrder("S-F", "ODIN", BloodhoundOrder.Status.Sent);
        BloodhoundOrder second = new BloodhoundOrder("S-G", "ODIN", BloodhoundOrder.Status.Sent);
        manager.addOrder(first);
        manager.addOrder(second);

        reply("Roger", "ODIN");
        assertEquals(BloodhoundOrder.Status.Sent, first.getStatus());
        assertEquals(BloodhoundOrder.Status.Sent, second.getStatus());

        reply("Roger S-F", "ODIN");
        assertEquals(BloodhoundOrder.Status.Bloodhounding, first.getStatus());
        assertEquals(BloodhoundOrder.Status.Sent, second.getStatus());
    }

    @Test
    public void wrongSenderAndPromptDoNotUpdateOrder() {
        BloodhoundOrder order = new BloodhoundOrder("S-F", "ODIN", BloodhoundOrder.Status.Sent);
        manager.addOrder(order);

        reply("Roger", "OTHER");
        reply("S-F RGR to start, nPos to close", "ODIN");
        reply("rgrs", "ODIN");
        reply("Roger S-G", "ODIN");
        assertEquals(BloodhoundOrder.Status.Sent, order.getStatus());
        reply("Bloodhonding S-F", "ODIN");
        assertEquals(BloodhoundOrder.Status.Bloodhounding, order.getStatus());
        reply("In Position S-F", "ODIN");
        assertEquals(BloodhoundOrder.Status.Complete, order.getStatus());
    }

    private void reply(String text, String sender) {
        Bundle message = mock(Bundle.class);
        when(message.getString("message")).thenReturn(text);
        when(message.getString("senderCallsign")).thenReturn(sender);
        manager.chatMessageReceived(message);
    }
}
