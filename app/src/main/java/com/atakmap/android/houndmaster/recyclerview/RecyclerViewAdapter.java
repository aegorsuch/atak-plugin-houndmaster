package com.atakmap.android.houndmaster.recyclerview;

import android.content.Context;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;

import com.atakmap.android.houndmaster.plugin.R;
import com.atakmap.android.maps.MapGroup;
import com.atakmap.android.maps.MapItem;
import com.atakmap.android.maps.MapTouchController;
import com.atakmap.android.maps.MapView;
import com.atakmap.android.math.MathUtils;
import com.atakmap.android.util.ATAKUtilities;
import com.atakmap.coremap.maps.time.CoordinatedTime;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * Adapter used to display content in a RecyclerView
 */
public class RecyclerViewAdapter extends RecyclerView.Adapter {

    private final MapView _mapView;
    private final LayoutInflater _inflater;
    private final List<MapItem> allItems = new ArrayList<>();
    private final List<MapItem> _items = new ArrayList<>();
    private boolean _listMode = true;
    private final boolean contactsOnly;
    private String query = "";

    private OnItemSelectedListener onItemSelectedListener;

    public RecyclerViewAdapter(MapView mapView, Context plugin) {
        this(mapView, plugin, false);
    }
    public RecyclerViewAdapter(MapView mapView, Context plugin, boolean contactsOnly) {
        _mapView = mapView;
        _inflater = LayoutInflater.from(plugin);
        this.contactsOnly = contactsOnly;

        refreshItems();
    }

    public void refreshItems() {
        allItems.clear();
        collectItems(_mapView.getRootGroup());
        Collections.sort(allItems, (a, b) -> {
            String first = a.getTitle() == null ? "" : a.getTitle();
            String second = b.getTitle() == null ? "" : b.getTitle();
            return first.compareToIgnoreCase(second);
        });
        filterItems();
    }

    public void setQuery(String query) {
        this.query = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        filterItems();
    }

    public void bindSearch(View picker) {
        EditText search = picker.findViewById(R.id.recyclerViewSearch);
        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                setQuery(text.toString());
            }

            @Override
            public void afterTextChanged(Editable text) {}
        });
    }

    private void filterItems() {
        _items.clear();
        for (MapItem item : allItems) {
            if (matchesQuery(item, query)) {
                _items.add(item);
            }
        }
        notifyDataSetChanged();
    }

    static boolean matchesQuery(MapItem item, String query) {
        if (query.isEmpty())
            return true;
        String title = item.getTitle();
        String callsign = item.getMetaString("callsign", null);
        return title != null && title.toLowerCase(Locale.ROOT).contains(query)
                || callsign != null && callsign.toLowerCase(Locale.ROOT).contains(query);
    }

    private void collectItems(MapGroup group) {
        for (MapItem item : group.getItems()) {
            if (isEligible(item, contactsOnly))
                allItems.add(item);
        }
        for (MapGroup grp : group.getChildGroups()) {
            collectItems(grp);
        }
    }

    public static boolean isEligible(MapItem item, boolean contactsOnly) {
        if (item == null)
            return false;
        boolean isContact = item.hasMetaValue("atakRoleType");
        if (contactsOnly)
            return isContact;
        String type = item.getType();
        return !isContact && (type != null && type.startsWith("a-")
                || "b-m-p-s-p-i".equals(type));
    }

    public void setListMode(boolean listMode) {
        _listMode = listMode;
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = _inflater.inflate(_listMode ? R.layout.marker_callsign_row
                : R.layout.marker_callsign_tile, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(@NonNull RecyclerView.ViewHolder rh, int pos) {
        if (!(rh instanceof ViewHolder))
            return;
        MapItem mi = _items.get(pos);
        ViewHolder h = (ViewHolder) rh;

        ATAKUtilities.SetIcon(_mapView.getContext(), h.icon, mi);

        h.callsign.setText(mi.getTitle());

        long now = new CoordinatedTime().getMilliseconds();
        h.lastUpdate.setText(MathUtils.GetTimeRemainingOrDateString(now,
                now - mi.getMetaLong("lastUpdateTime", 0), true));
    }

    @Override
    public int getItemCount() {
        return _items.size();
    }

    private class ViewHolder extends RecyclerView.ViewHolder
            implements View.OnClickListener {

        final ImageView icon;
        final TextView callsign;
        final TextView lastUpdate;

        public ViewHolder(View v) {
            super(v);
            icon = v.findViewById(R.id.icon);
            callsign = v.findViewById(R.id.callsign);
            lastUpdate = v.findViewById(R.id.last_update);
            v.setOnClickListener(this);
        }

        @Override
        public void onClick(View v) {
            int pos = getAdapterPosition();
            if (pos < 0 || pos >= getItemCount())
                return;
            MapItem item = _items.get(pos);
            MapTouchController.goTo(item, true);
            if (onItemSelectedListener != null) {
                onItemSelectedListener.onItemSelected(item);
            }
        }
    }

    public void setOnItemSelectedListener(OnItemSelectedListener listener) {
        this.onItemSelectedListener = listener;
    }
    public interface OnItemSelectedListener {
        void onItemSelected(MapItem item);
    }
}
