package com.atakmap.android.houndmaster.recyclerview;

import com.atakmap.android.maps.MapItem;

import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

public class RecyclerViewAdapterTest {
    @Test
    public void separatesMapTargetsFromContacts() {
        MapItem target = mock(MapItem.class);
        when(target.getType()).thenReturn("a-h-G");
        assertTrue(RecyclerViewAdapter.isEligible(target, false));
        assertFalse(RecyclerViewAdapter.isEligible(target, true));

        MapItem contact = mock(MapItem.class);
        when(contact.getType()).thenReturn("a-f-G");
        when(contact.hasMetaValue("atakRoleType")).thenReturn(true);
        assertTrue(RecyclerViewAdapter.isEligible(contact, true));
        assertFalse(RecyclerViewAdapter.isEligible(contact, false));
    }

    @Test
    public void searchesTitleOrCallsign() {
        MapItem contact = mock(MapItem.class);
        when(contact.getTitle()).thenReturn("Team Lead");
        when(contact.getMetaString("callsign", null)).thenReturn("ODIN");

        assertTrue(RecyclerViewAdapter.matchesQuery(contact, "team"));
        assertTrue(RecyclerViewAdapter.matchesQuery(contact, "odin"));
        assertFalse(RecyclerViewAdapter.matchesQuery(contact, "other"));
    }
}
