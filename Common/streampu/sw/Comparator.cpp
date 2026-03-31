#include "Comparator.hpp"

using namespace spu;
using namespace spu::module;

Comparator::Comparator(int frame_size)
    : Stateful(), frame_size(frame_size), n_errors_total(0), n_frames(0)
{
    this->set_name("Comparator");
    this->set_short_name("Comparator");

    auto &t    = this->create_task("check");
    auto p_ref = this->create_socket_in<int>(t, "in_ref", frame_size);
    auto p_got = this->create_socket_in<int>(t, "in_got", frame_size);

    this->create_codelet(t, [p_ref, p_got](Module &m, runtime::Task &t, const size_t /*frame_id*/) -> int {
        auto &self     = static_cast<Comparator&>(m);
        const int* ref = static_cast<const int*>(t[p_ref].get_dataptr());
        const int* got = static_cast<const int*>(t[p_got].get_dataptr());

        int errors = 0;
        for (int i = 0; i < self.frame_size; i++)
            if (ref[i] != got[i]) errors++;

        self.n_errors_total += errors;
        self.n_frames++;
        return runtime::status_t::SUCCESS;
    });
}

Comparator::~Comparator() = default;

int Comparator::get_n_errors() const
{
    return n_errors_total;
}

int Comparator::get_frame_count() const
{
    return n_frames;
}

bool Comparator::has_errors() const
{
    return n_errors_total > 0;
}