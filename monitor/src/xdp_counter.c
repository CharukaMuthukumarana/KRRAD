#include <uapi/linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>

struct metrics_t {
    u64 packets;
    u64 bytes;
};

// Existing Maps
BPF_HASH(metrics_map, u32, struct metrics_t);
BPF_HASH(blacklist, u32, u8);

// Track Packets per Source IP
BPF_HASH(ip_tracker, u32, u64);

int xdp_prog(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)eth + sizeof(*eth) > data_end) return XDP_PASS;

    if (eth->h_proto != bpf_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = data + sizeof(*eth);
    if ((void *)ip + sizeof(*ip) > data_end) return XDP_PASS;

    // Check Blacklist (Existing Logic)
    u32 src_ip = ip->saddr;
    u8 *blocked = blacklist.lookup(&src_ip);
    if (blocked) {
        return XDP_DROP;
    }

    // Update Protocol Metrics (Existing Logic)
    u32 protocol = ip->protocol;
    u64 packet_len = (u64)(data_end - data);
    struct metrics_t zero = {0, 0};
    struct metrics_t *val = metrics_map.lookup_or_try_init(&protocol, &zero);
    if (val) {
        lock_xadd(&val->packets, 1);
        lock_xadd(&val->bytes, packet_len);
    }

    // Count this specific IP
    u64 zero_ip = 0;
    u64 *ip_count = ip_tracker.lookup_or_try_init(&src_ip, &zero_ip);
    if (ip_count) {
        lock_xadd(ip_count, 1);
    }

    return XDP_PASS;
}