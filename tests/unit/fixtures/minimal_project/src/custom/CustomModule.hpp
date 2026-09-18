#pragma once

#include <streampu.hpp>

class CustomModule : public spu::module::Stateful
{
private:
    int frame_size;

public:
    explicit CustomModule(int frame_size);
    CustomModule* clone() const override;

private:
    void process(const int* input, int* output);
};
