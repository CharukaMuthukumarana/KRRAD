// monitor/src/xdp_counter.c
#include <uapi/linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>

// 1. Map for Packet Counting (Metrics)
BPF_HASH(packet_counts, u32, u64);

// 2. Map for Blacklisted IPs (Mitigation)
// Key: Source IP (u32), Value: 1 (Drop) or 0 (Pass)
BPF_HASH(blacklist, u32, u8);

int xdp_prog(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)eth + sizeof(*eth) > data_end)
        return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)ip + sizeof(*ip) > data_end)
        return XDP_PASS;

    // --- LOGIC 1: CHECK BLACKLIST (Mitigation) ---
    u32 src_ip = ip->saddr;
    u8 *blocked = blacklist.lookup(&src_ip);
    if (blocked) {
        // If IP is in blacklist, DROP the packet immediately
        return XDP_DROP;
    }

    // --- LOGIC 2: COUNT TRAFFIC (Monitoring) ---
    u32 protocol = ip->protocol;
    u64 zero = 0;
    u64 *count = packet_counts.lookup_or_try_init(&protocol, &zero);
    if (count) {
        lock_xadd(count, 1);
    }

    return XDP_PASS;
}